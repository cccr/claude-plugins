#!/usr/bin/env python3
"""Regenerate skills/plain-writing/SKILL.md from scripts/patterns.json.

Keeps the prevention layer (skill) and the enforcement layer (hook) in sync:
edit patterns.json, run this script, done.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

EXAMPLES = [
    ("negation pair", "No fluff, no filler, just results.", "Here are the results."),
    ("not just X, it's Y", "It's not just a tool, it's a workflow.", "It's a tool that also changes how you work."),
    ("X isn't A, it's B", "This isn't a bug, it's a design choice.", "This was a design choice."),
    ("stock phrase", "Let's dive into the details.", "Here are the details."),
]


def main():
    with open(os.path.join(HERE, "patterns.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    labels = [p["label"] for p in cfg["patterns"]]
    out = [
        "---",
        "name: plain-writing",
        "description: Use when writing or editing any narrative prose (answers, summaries, emails, posts, reports) so it sounds like a person wrote it. Avoids negation pairs (\"no X, no Y\"), \"not just X, it's Y\", stock phrases and em-dash overuse.",
        "---",
        "",
        "# Plain writing",
        "",
        "Write the way a person would say it out loud. Before sending any prose, check it against the list below.",
        "",
        "## Rules",
        "",
    ]
    out += ["- " + b for b in cfg["style_brief"]]
    out += ["", "## Patterns to avoid", ""]
    out += ["- " + l for l in labels]
    out += ["- more than a couple of em dashes per reply", "", "## Examples", ""]
    for name, bad, good in EXAMPLES:
        out.append("- %s: \"%s\" -> \"%s\"" % (name, bad, good))
    out += [
        "",
        "## Scope",
        "",
        "Applies to prose only. Leave code, quotes, commands, file paths and anything the "
        "user asked to be reproduced verbatim untouched. Never change facts, numbers or names "
        "while rewording.",
        "",
    ]
    path = os.path.join(ROOT, "skills", "plain-writing", "SKILL.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("wrote", path)


if __name__ == "__main__":
    main()
