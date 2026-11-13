# anti-slop

Catches common AI-writing tells in Claude's final reply and gets them rewritten in plain, natural wording.

## What it does

1. **Stop hook (Claude Code surfaces).** After Claude finishes, `scripts/detect.py` scans only the final message for patterns such as "no X, no Y", "not just X, it's Y", "this isn't A, it's B", stock phrases ("let's dive in", "delve") and em-dash overuse. Code blocks, quotes, URLs and tables are ignored.
2. **Small rewriter.** If enough patterns hit, a headless `claude -p --model haiku` call drafts plain replacements for the flagged sentences. Claude then receives them as a block reason and re-sends its answer with only those sentences changed.
3. **Prevention skill (everywhere skills load).** `plain-writing` carries the same rules so the text is cleaner before the hook ever fires.

## Install (Claude Code)

    /plugin install anti-slop --marketplace cccr/claude-plugins

Or try it for one session from a local checkout:

    claude --plugin-dir /path/to/anti-slop

Restart the session after installing, because hooks load at session start.

## Settings

Edit `scripts/patterns.json` to add or tune patterns, weights, the trigger score and the minimum word count. After editing run `python3 scripts/build_skill.py` to refresh the skill text.

Environment switches:

- `ANTISLOP=off` disables the hook.
- `ANTISLOP_REWRITE=0` skips the Haiku call and only lists the flagged sentences.
- `ANTISLOP_MODEL=<name>` picks a different rewriter model (default `haiku`).
- `ANTISLOP_DEBUG=1` logs decisions to stderr.

## Safety

The hook fails open: any error, timeout or missing `claude` binary lets the reply through untouched. It checks `stop_hook_active` so it runs at most once per turn, and sets `ANTISLOP_INNER=1` for the rewriter call so it cannot trigger itself.

## Limits

Hooks cannot edit a reply that has already been shown, so the corrected version appears as a follow-up message. Plain claude.ai chat and the mobile app do not run hooks; there only the skill applies.

## Tests

    python3 -m unittest discover -s tests -v
