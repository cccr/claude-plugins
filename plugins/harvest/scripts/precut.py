#!/usr/bin/env python3
"""Cut a Claude Code transcript down to what a lessons harvest needs. No model involved.

Kept: typed user messages, assistant text, each tool call as one line, the last 30 lines of
failed tool results, the header (up to a line of 40 dashes, at most 30 lines) of results that
start with one of the given prefixes. Dropped: successful tool output, thinking, reminders,
attachments, skill bodies. Subagent transcripts (<session>/subagents/*.jsonl) follow the main
one under their description. Only bytes after the stored offsets are read, and only up to the
last complete line, so a transcript still being written loses nothing.
"""
import glob
import json
import os
import re

REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
ERROR_TAIL = 30
CALL_CHARS = 200


def read_new(path, offset):
    with open(path, "rb") as f:
        f.seek(offset)
        data = f.read()
    end = data.rfind(b"\n") + 1
    entries = []
    for raw in data[:end].splitlines():
        try:
            entries.append(json.loads(raw))
        except ValueError:
            continue
    return entries, offset + end


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def call_summary(name, args):
    for key in ("command", "file_path", "pattern", "url", "description", "prompt"):
        if isinstance(args.get(key), str):
            return f"CALL {name}: {args[key][:CALL_CHARS]}".rstrip()
    return f"CALL {name}: {json.dumps(args)[:CALL_CHARS]}"


def kept_header(text, prefixes):
    for prefix in prefixes:
        if text.startswith(prefix):
            head = text.split("\n" + "-" * 40)[0]
            return prefix.rstrip(":").upper() + ": " + "\n".join(head.splitlines()[:ERROR_TAIL])
    return None


def cut_entries(entries, keep_prefixes=()):
    items = []
    for e in entries:
        kind = e.get("type")
        content = (e.get("message") or {}).get("content")
        if kind == "user" and not e.get("isMeta"):
            if isinstance(content, str) or (isinstance(content, list) and
                                            all(b.get("type") == "text" for b in content if isinstance(b, dict))):
                t = REMINDER.sub("", text_of(content)).strip()
                if t:
                    items.append(f"USER: {t}")
                continue
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict) or b.get("type") != "tool_result":
                    continue
                t = text_of(b.get("content"))
                if b.get("is_error"):
                    items.append("ERROR: " + "\n".join(t.splitlines()[-ERROR_TAIL:]))
                else:
                    head = kept_header(t, keep_prefixes)
                    if head:
                        items.append(head)
        elif kind == "assistant" and isinstance(content, list):
            for b in content:
                if b.get("type") == "text" and b.get("text", "").strip():
                    items.append(f"ASSISTANT: {b['text'].strip()}")
                elif b.get("type") == "tool_use":
                    items.append(call_summary(b.get("name", "?"), b.get("input") or {}))
    return items


def subagent_files(transcript):
    folder = os.path.join(os.path.splitext(transcript)[0], "subagents")
    return sorted(glob.glob(os.path.join(folder, "*.jsonl")))


def description(jsonl):
    try:
        with open(os.path.splitext(jsonl)[0] + ".meta.json") as f:
            return json.load(f).get("description") or os.path.basename(jsonl)
    except (OSError, ValueError):
        return os.path.basename(jsonl)


def precut(transcript, offsets, cap=60000, keep_prefixes=()):
    new_offsets = dict(offsets)
    items = []
    for i, path in enumerate([transcript] + subagent_files(transcript)):
        key = os.path.abspath(path)
        entries, new_offsets[key] = read_new(path, offsets.get(key, 0))
        cut = cut_entries(entries, keep_prefixes)
        if cut and i > 0:
            items.append(f"=== SUBAGENT: {description(path)} ===")
        items.extend(cut)
    dropped = 0
    while items and sum(len(x) + 1 for x in items) > cap:
        items.pop(0)
        dropped += 1
    text = "\n".join(items)
    if dropped:
        text = f"[cut: {dropped} older items dropped to fit {cap} characters]\n" + text
    return text, new_offsets
