#!/usr/bin/env python3
"""anti-slop Stop hook.

Reads the Stop-hook JSON from stdin, scans the final assistant message for
common AI-writing tells, and (if enough are found) blocks the stop with a
reason that asks Claude to re-send the answer with those sentences reworded.
A small headless `claude -p --model haiku` call drafts the replacements so the
main model gets concrete wording instead of a vague instruction.

Design rules:
  * Fail open: any error -> exit 0 silently, never trap the user.
  * One pass only: honours stop_hook_active.
  * Never recurse: the inner claude call sets ANTISLOP_INNER=1.
  * Stdlib only.

Env switches:
  ANTISLOP=off            disable entirely
  ANTISLOP_REWRITE=0      skip the Haiku call; just flag the sentences
  ANTISLOP_MODEL=<name>   model for the rewriter (default: haiku)
  ANTISLOP_DEBUG=1        log decisions to stderr
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PATTERNS_FILE = os.path.join(HERE, "patterns.json")


def debug(msg):
    if os.environ.get("ANTISLOP_DEBUG") == "1":
        sys.stderr.write("[anti-slop] %s\n" % msg)


def load_config(path=PATTERNS_FILE):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    for p in cfg["patterns"]:
        p["_re"] = re.compile(p["regex"], re.IGNORECASE)
    return cfg


# ---------------------------------------------------------------- text prep

def narrative_only(text):
    """Remove everything that is not prose: code, quotes, URLs, tables."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"~~~.*?~~~", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`\n]*`", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(">") or s.startswith("|"):
            continue
        s = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", s)  # bullet / number markers
        s = re.sub(r"^#{1,6}\s+", "", s)             # heading markers
        s = s.replace("**", "").replace("__", "")
        lines.append(s)
    return "\n".join(lines)


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p and p.strip()]


def word_count(text):
    return len(re.findall(r"\w+", text))


# ---------------------------------------------------------------- analysis

def analyze(message, cfg):
    s = cfg["settings"]
    prose = narrative_only(message)
    words = word_count(prose)
    result = {"words": words, "score": 0, "flagged": [], "notes": [], "sentences": []}
    if words < s["min_words"]:
        return result

    sentences = split_sentences(prose)
    result["sentences"] = sentences
    score = 0
    for i, sent in enumerate(sentences):
        hits = []
        for p in cfg["patterns"]:
            if p["_re"].search(sent):
                hits.append(p)
        if hits:
            score += sum(h["weight"] for h in hits)
            result["flagged"].append(
                {"index": i, "sentence": sent, "labels": [h["label"] for h in hits]}
            )

    dashes = prose.count("—")
    density = dashes * 100.0 / max(words, 1)
    if dashes >= 3 and density > s["em_dash_per_100_words"]:
        score += s["em_dash_weight"]
        result["notes"].append(
            "Too many em dashes (%d). Use commas, periods or parentheses instead." % dashes
        )

    result["score"] = score
    return result


# ---------------------------------------------------------------- rewriter

def draft_rewrites(result, cfg):
    """Ask a small model for plain replacements. Returns {n: text} (1-based)."""
    if os.environ.get("ANTISLOP_REWRITE") == "0" or not result["flagged"]:
        return {}
    flagged = result["flagged"][: cfg["settings"]["max_flagged_sentences"]]
    sents = result["sentences"]
    blocks = []
    for n, f in enumerate(flagged, 1):
        i = f["index"]
        before = sents[i - 1] if i > 0 else ""
        after = sents[i + 1] if i + 1 < len(sents) else ""
        blocks.append(
            "%d.\nBEFORE: %s\nSENTENCE: %s\nAFTER: %s" % (n, before, f["sentence"], after)
        )
    brief = "\n".join("- " + b for b in cfg["style_brief"])
    prompt = (
        "You are a copy editor. Rewrite each SENTENCE so it sounds like something a "
        "person would actually say. BEFORE and AFTER are context only; do not rewrite "
        "them and do not repeat them.\n\nRules:\n%s\n\n"
        "Reply with exactly one line per item, formatted `N. rewritten sentence`. "
        "No preamble, no commentary, no quotes.\n\n%s\n" % (brief, "\n\n".join(blocks))
    )
    env = dict(os.environ, ANTISLOP_INNER="1")
    model = os.environ.get("ANTISLOP_MODEL", "haiku")
    try:
        proc = subprocess.run(
            ["claude", "-p", "--model", model],
            input=prompt, capture_output=True, text=True, timeout=30, env=env,
        )
    except Exception as e:  # missing binary, timeout, ...
        debug("rewriter failed: %r" % (e,))
        return {}
    if proc.returncode != 0:
        debug("rewriter exit %s: %s" % (proc.returncode, proc.stderr[:200]))
        return {}
    out = {}
    for line in proc.stdout.splitlines():
        m = re.match(r"^\s*(\d+)[.)]\s+(.+?)\s*$", line)
        if m:
            out[int(m.group(1))] = m.group(2).strip("\"'“”")
    return out


# ---------------------------------------------------------------- output

def build_reason(result, rewrites, cfg):
    flagged = result["flagged"][: cfg["settings"]["max_flagged_sentences"]]
    lines = [
        "Style check: your last reply has wording that reads as machine-written.",
        "Send your previous answer again in full, changing only the sentences listed "
        "below (same facts, same order, same formatting). Output only the corrected "
        "answer. Do not mention this check or say you rewrote anything.",
        "",
        "Style brief:",
    ]
    lines += ["- " + b for b in cfg["style_brief"]]
    lines += ["", "Sentences to fix:"]
    for n, f in enumerate(flagged, 1):
        lines.append("%d. [%s] %s" % (n, "; ".join(f["labels"]), f["sentence"]))
        if n in rewrites:
            lines.append("   Suggested: %s" % rewrites[n])
    for note in result["notes"]:
        lines.append("")
        lines.append("Also: " + note)
    return "\n".join(lines)


def main():
    if os.environ.get("ANTISLOP") == "off" or os.environ.get("ANTISLOP_INNER") == "1":
        return 0
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("stop_hook_active"):
        debug("second pass, letting it through")
        return 0
    message = data.get("last_assistant_message") or ""
    if not message.strip():
        return 0
    try:
        cfg = load_config()
        result = analyze(message, cfg)
        debug("words=%d score=%d flagged=%d" % (result["words"], result["score"], len(result["flagged"])))
        if result["score"] < cfg["settings"]["trigger_score"]:
            return 0
        rewrites = draft_rewrites(result, cfg)
        reason = build_reason(result, rewrites, cfg)
    except Exception as e:
        debug("error: %r" % (e,))
        return 0
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
