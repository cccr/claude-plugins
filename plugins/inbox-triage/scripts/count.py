#!/usr/bin/env python3
"""SessionStart hook: say how many harvested entries wait in the project's inbox.

    python3 count.py --hook   (hook JSON on stdin)
    python3 count.py ROOT     (prints the same line, for a manual check)

The inbox is <dir>/inbox.md, <dir> from ROOT/.claude/harvest.json (default behind_the_scenes),
the file the harvest plugin fills. With no config, or nothing waiting, it prints nothing.
"""
import json
import os
import sys

CONFIG = os.path.join(".claude", "harvest.json")


def inbox_path(root):
    try:
        with open(os.path.join(root, CONFIG), encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(config, dict):
        return None
    return os.path.join(root, config.get("dir", "behind_the_scenes"), "inbox.md")


def count(path):
    try:
        with open(path, encoding="utf-8") as f:
            return sum(1 for line in f if line.startswith("- ["))
    except OSError:
        return 0


def note(root):
    path = inbox_path(root)
    n = count(path) if path else 0
    if not n:
        return ""
    shown = os.path.relpath(path, root)
    return (f"{n} harvested {'entry waits' if n == 1 else 'entries wait'} in {shown}. "
            "At the start of this session, tell the user how many and offer to sort them with the "
            "inbox-triage:triage skill. Nothing is promoted without the user's yes.")


def main(argv, stdin=sys.stdin, env=os.environ):
    if argv[1:] == ["--hook"]:
        try:
            payload = json.loads(stdin.read())
            root = env.get("CLAUDE_PROJECT_DIR") or payload["cwd"]
        except (ValueError, KeyError, TypeError):
            return 0
    elif len(argv) == 2:
        root = argv[1]
    else:
        print(__doc__, file=sys.stderr)
        return 2
    text = note(root)
    if text:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
