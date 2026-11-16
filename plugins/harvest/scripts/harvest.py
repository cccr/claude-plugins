#!/usr/bin/env python3
"""Harvest lessons, decisions and results from a Claude Code session into a private inbox.

    python3 harvest.py --hook                      (SessionEnd / PreCompact hook)
    python3 harvest.py ROOT SESSION_ID TRANSCRIPT  (foreground, for a manual run)

A project opts in with ROOT/.claude/harvest.json (see the plugin README); without it nothing
runs. The hook form reads the hook JSON on stdin, starts the harvest in its own session so ending
Claude Code does not stop it, and returns at once. The harvest cuts the new part of the
transcript down (precut.py), asks a headless `claude -p` for entries, and appends them to
<dir>/inbox.md. Nothing else in the project is written. Errors go to <dir>/harvest.log; a failed
run leaves the offsets alone so the next one retries. HARVEST_CHILD=1 marks the harvest's own
process tree: the hook does nothing there. HARVEST_DIR and HARVEST_CLAUDE override the inbox
folder and the claude binary.
"""
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import precut  # noqa: E402

CONFIG = os.path.join(".claude", "harvest.json")
MIN_CHARS = 2000
CAP = 60000
TIMEOUT = 300
STALE_LOCK = 30 * 60
LOCK_WAIT = 10 * 60
MODEL_ARGS = ["-p", "--setting-sources", "user", "--tools", "", "--no-session-persistence"]
DEFAULTS = {
    "dir": "behind_the_scenes",
    "known": [],
    "kinds": {
        "lesson": "a gotcha, a behaviour that surprised, a rule it left",
        "decision": "a choice made, with the alternative not taken",
        "result": "a measured number with its conditions (what, where, how)",
    },
    "tags": {"any": "anywhere in this project"},
    "keep_result_prefixes": [],
    "model": "sonnet",
}


def load_config(root):
    """The project's harvest.json over the defaults, or None when the project has not opted in."""
    try:
        with open(os.path.join(root, CONFIG), encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(config, dict) or not config.get("project"):
        return None
    return dict(DEFAULTS, **config)


def entry_pattern(config):
    kinds = "|".join(map(re.escape, config["kinds"]))
    tags = "|".join(map(re.escape, config["tags"]))
    return re.compile(rf"^- \[({kinds})\]\[({tags})\] ")


def listing(d):
    return "\n".join(f"- {k}: {v}" for k, v in d.items())


def render_prompt(config, known, text):
    with open(os.path.join(HERE, "prompt.md"), encoding="utf-8") as f:
        template = f.read()
    return (template.replace("{{PROJECT}}", config["project"])
            .replace("{{KINDS}}", listing(config["kinds"]))
            .replace("{{TAGS}}", listing(config["tags"]))
            .replace("{{KNOWN}}", known)
            .replace("{{TRANSCRIPT}}", text))


def known_entries(root, patterns):
    found = []
    files = []
    for pattern in patterns:
        files += sorted(glob.glob(os.path.join(root, pattern)))
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("### "):
                        found.append("- " + line[4:].strip())
                    else:
                        m = re.match(r"^\| (\d+) \| (.*?) \|", line)
                        if m:
                            found.append(f"- decision {m.group(1)}: {m.group(2)}")
        except OSError:
            continue
    return "\n".join(found) or "(none yet)"


def log(bts, message):
    with open(os.path.join(bts, "harvest.log"), "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")


def take_lock(path, wait):
    """Take the lock, waiting up to `wait` seconds for another harvest to finish."""
    deadline = time.time() + wait
    while True:
        try:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(path) > STALE_LOCK:
                    os.remove(path)
                    continue
            except OSError:
                continue
        if time.time() >= deadline:
            return False
        time.sleep(0.2)


def queue(bts, session_id, transcript):
    with open(os.path.join(bts, "harvest-pending.txt"), "a", encoding="utf-8") as f:
        f.write(f"{session_id}\t{transcript}\n")


def take_pending(bts):
    """Sessions an earlier run could not finish, oldest first, once each; the list is emptied."""
    path = os.path.join(bts, "harvest-pending.txt")
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
        os.remove(path)
    except OSError:
        return []
    jobs = {}
    for line in lines:
        sid, _, transcript = line.partition("\t")
        if transcript:
            jobs[transcript] = sid
    return [(sid, t) for t, sid in jobs.items()]


def harvest_one(session_id, transcript, bts, claude, root):
    """Harvest the new part of one transcript. 0 done or nothing to do, 1 failed (offsets kept)."""
    try:
        state_path = os.path.join(bts, "harvest-state.json")
        try:
            with open(state_path) as f:
                state = json.load(f)
        except (OSError, ValueError):
            state = {}
        config = load_config(root)
        if config is None:
            return 0
        text, offsets = precut.precut(transcript, state, CAP, config["keep_result_prefixes"])

        def save():
            tmp = state_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(offsets, f, indent=1)
            os.replace(tmp, state_path)

        if len(text) < MIN_CHARS:
            save()
            return 0
        prompt = render_prompt(config, known_entries(root, config["known"]), text)
        env = dict(os.environ, HARVEST_CHILD="1")
        r = subprocess.run([claude] + MODEL_ARGS + ["--model", config["model"]], input=prompt, capture_output=True, text=True,
                           timeout=TIMEOUT, env=env, cwd=tempfile.gettempdir())
        if r.returncode != 0:
            log(bts, f"{session_id[:8]} failed: exit {r.returncode}: {r.stderr.strip()[-500:]}")
            return 1
        entry = entry_pattern(config)
        entries = [line.rstrip() for line in r.stdout.splitlines() if entry.match(line)]
        if entries:
            with open(os.path.join(bts, "inbox.md"), "a", encoding="utf-8") as f:
                f.write(f"## {datetime.now():%Y-%m-%d %H:%M}, session {session_id[:8]}\n\n")
                f.write("\n".join(entries) + "\n\n")
        save()
        return 0
    except subprocess.TimeoutExpired:
        log(bts, f"{session_id[:8]} failed: model timed out after {TIMEOUT} s")
        return 1
    except Exception as e:  # a hook must never surface a traceback into a session
        log(bts, f"{session_id[:8]} failed: {e!r}")
        return 1


def run(session_id, transcript, bts, claude, root, lock_wait=LOCK_WAIT):
    """Harvest this session, and any an earlier run skipped or failed. A session that cannot be
    done now (lock held too long, model failed) is queued and retried by the next run."""
    os.makedirs(bts, exist_ok=True)
    lock = os.path.join(bts, "harvest.lock")
    if not take_lock(lock, lock_wait):
        queue(bts, session_id, transcript)
        log(bts, f"{session_id[:8]} queued: another harvest held the lock for {lock_wait} s")
        return 0
    try:
        jobs = [j for j in take_pending(bts) if j[1] != transcript and os.path.exists(j[1])]
        rc = 0
        for sid, path in jobs + [(session_id, transcript)]:
            if harvest_one(sid, path, bts, claude, root) != 0:
                queue(bts, sid, path)
                if path == transcript:
                    rc = 1
        return rc
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass


def spawn_detached(argv):
    subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True, cwd=argv[2])


def hook(stdin_text, spawn=spawn_detached, env=None):
    env = os.environ if env is None else env
    if env.get("HARVEST_CHILD") == "1":
        return 0
    try:
        payload = json.loads(stdin_text)
        session_id, transcript = payload["session_id"], payload["transcript_path"]
        root = env.get("CLAUDE_PROJECT_DIR") or payload["cwd"]
    except (ValueError, KeyError, TypeError):
        return 0
    if load_config(root) is None:
        return 0
    spawn([sys.executable, os.path.abspath(__file__), root, session_id, transcript])
    return 0


def main(argv):
    if argv[1:] == ["--hook"]:
        return hook(sys.stdin.read())
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    root = os.path.abspath(argv[1])
    config = load_config(root)
    if config is None:
        print(f"no {CONFIG} with a \"project\" in {root}", file=sys.stderr)
        return 2
    bts = os.environ.get("HARVEST_DIR", os.path.join(root, config["dir"]))
    claude = os.environ.get("HARVEST_CLAUDE", "claude")
    return run(argv[2], argv[3], bts, claude, root)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
