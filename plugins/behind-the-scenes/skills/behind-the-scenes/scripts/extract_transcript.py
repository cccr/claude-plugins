#!/usr/bin/env python3
"""Helpers for mining Claude Code session .jsonl transcripts.

Two subcommands:

  scan <dir>
      List every *.jsonl in <dir> with line count, first/last timestamp,
      and a short preview of the first substantive user message. Use this
      to triage which sessions exist and decide what's worth writing up
      before spending any tokens reading them.

  extract <src.jsonl> <dst.md> <title>
      Write a condensed, human-readable transcript to <dst.md>: every
      user/assistant text block verbatim and in order, tool_use calls
      collapsed to a one-line signature, tool_result payloads truncated to
      a short preview. This keeps the file readable instead of dumping raw
      API/file payloads, while still being close enough to verbatim to
      pull exact quotes from.

Both subcommands only ever touch the files you point them at — they never
guess at paths themselves.
"""
import json
import sys


def _first_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "")
    return None


def cmd_scan(directory):
    import glob
    import os

    files = sorted(glob.glob(os.path.join(directory, "*.jsonl")))
    if not files:
        print(f"(no .jsonl files in {directory})")
        return
    for path in files:
        first_ts = last_ts = None
        first_user = None
        n = 0
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                n += 1
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                ts = d.get("timestamp")
                if ts:
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts
                if first_user is None and d.get("type") == "user":
                    t = _first_text(d.get("message", {}).get("content"))
                    if t and "<local-command-caveat>" not in t[:40]:
                        first_user = t[:200].replace("\n", " ")
        print(f"=== {os.path.basename(path)} ===")
        print(f"  lines: {n}")
        print(f"  span: {first_ts} -> {last_ts}")
        print(f"  first user message: {first_user!r}")
        print()


def _tool_text(content):
    out = []
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    for block in content:
        if not isinstance(block, dict):
            continue
        t = block.get("type")
        if t == "text":
            out.append(block.get("text", ""))
        elif t == "tool_use":
            name = block.get("name", "?")
            try:
                inp_s = json.dumps(block.get("input", {}))
            except Exception:
                inp_s = str(block.get("input", {}))
            if len(inp_s) > 220:
                inp_s = inp_s[:220] + "…"
            out.append(f"\n> **[tool call: {name}]** `{inp_s}`\n")
        elif t == "tool_result":
            c = block.get("content", "")
            if isinstance(c, list):
                c = " ".join(
                    b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"
                )
            c = str(c).strip().replace("\n", " ")
            if len(c) > 300:
                c = c[:300] + "…"
            out.append(f"\n> *[tool result]* {c}\n")
    return "\n".join(x for x in out if x)


def cmd_extract(src, dst, title):
    lines_out = [f"# Raw transcript — {title}\n"]
    with open(src) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            typ = d.get("type")
            if typ not in ("user", "assistant"):
                continue
            body = _tool_text(d.get("message", {}).get("content"))
            if not body.strip():
                continue
            ts = d.get("timestamp", "")
            role = "USER" if typ == "user" else "ASSISTANT"
            lines_out.append(f"\n---\n**{role}** `{ts}`\n\n{body}\n")
    with open(dst, "w") as f:
        f.write("\n".join(lines_out))
    print(f"wrote {dst} ({len(lines_out)} blocks)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sub = sys.argv[1]
    if sub == "scan" and len(sys.argv) == 3:
        cmd_scan(sys.argv[2])
    elif sub == "extract" and len(sys.argv) == 5:
        cmd_extract(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
