# inbox-triage

Pairs with the `harvest` plugin.

- **SessionStart hook** (`scripts/count.py`): if `.claude/harvest.json` exists and its inbox
  (`<dir>/inbox.md`, default `behind_the_scenes/inbox.md`) has entries, it adds one line to the
  session's context: how many entries are waiting, and to offer sorting them. Otherwise it says
  nothing. Check it by hand with `python3 scripts/count.py ROOT`.
- **`triage` skill** (`/inbox-triage:triage`, or "sort the inbox"): goes through the entries in
  batches. For each one it proposes promote (exact text and destination file), merge into an
  existing entry, or drop. **Nothing is written without your yes.** Handled entries, and empty
  session headers, are removed from the inbox. Skipped ones stay.

## Where entries go

Set `destinations` in `.claude/harvest.json` to a sentence or two of mapping, for example:

```json
"destinations": "[any]/[idf] lessons and decisions in docs/lessons.md / docs/decisions.md; board-only ones in that board's docs/; bench results in the board's docs/results.md."
```

Without it, the skill looks for such a rule in `CLAUDE.md`, and asks if there isn't one.

## Tests

    python3 -m unittest discover -s tests
