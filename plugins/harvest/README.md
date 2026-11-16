# harvest

When a session ends, or is about to be compacted, this plugin cuts the new part of its
transcript down (no model involved) and asks a headless `claude -p` what a later session should
not have to learn again. The answers go into a private inbox as one line per entry:

    ## 2026-10-14 21:22, session f6f17a57

    - [lesson][tab5] The display needed setRotation(3), not 1. **Why:** found by eye on hardware.

Nothing else in the project is written. Sorting the inbox is the `inbox-triage` plugin's job.

## Opt in: `.claude/harvest.json`

Without this file, or without `project` in it, the hooks do nothing.

```json
{
  "project": "Dipstick, ESP-IDF firmware that turns an M5Stack board into a USB rescue console ...",
  "dir": "behind_the_scenes",
  "known": ["docs/lessons.md", "*/docs/lessons.md", "docs/decisions.md", "*/docs/decisions.md"],
  "kinds": {"lesson": "a gotcha, ...", "decision": "a choice made, ...", "result": "a bench number ..."},
  "tags": {"any": "any Dipstick, whatever the chip", "idf": "any ESP-IDF chip"},
  "keep_result_prefixes": ["logcut:"],
  "model": "sonnet"
}
```

| Key | Default | Meaning |
|---|---|---|
| `project` | required | One line naming and describing the project; it goes into the prompt |
| `dir` | `behind_the_scenes` | Folder for the inbox and the harvest's own files, relative to the project. Keep it git-ignored |
| `known` | `[]` | Globs of files whose `### ` headings and `\| N \| title \|` table rows are already-known entries; the model skips those |
| `kinds` | lesson, decision, result | `KIND: what it means`. Lines with another kind are dropped |
| `tags` | `{"any": ...}` | `TAG: how far it carries`. Lines with another tag are dropped |
| `keep_result_prefixes` | `[]` | Tool results starting with one of these keep their header (up to a line of 40 dashes, at most 30 lines); other successful results are dropped |
| `model` | `sonnet` | Model for the headless run |
| `destinations` | none | Not read here; `inbox-triage` uses it |

## What it writes, in `<dir>`

| File | |
|---|---|
| `inbox.md` | The entries, one `##` block per run that found something |
| `harvest-state.json` | Bytes already read, per transcript (and per subagent transcript) |
| `harvest.log` | Failures only |
| `harvest-pending.txt` | Sessions to retry: a failed run, or one that waited more than 10 minutes for the lock |
| `harvest.lock` | Held while a harvest runs; taken over after 30 minutes |

## How it runs

- The hook reads the hook JSON, takes the project root from `CLAUDE_PROJECT_DIR` (else the
  payload's `cwd`), checks the config, starts `harvest.py ROOT SESSION TRANSCRIPT` detached in its
  own session, and returns at once, so quitting Claude Code doesn't stop it.
- `precut.py` keeps typed user messages, assistant text, one line per tool call, the last 30
  lines of failed tool results, and the kept headers. Thinking, reminders, attachments and skill
  bodies are dropped. Subagent transcripts follow under their description. The text is capped
  at 60,000 characters, with the oldest items dropped first. Under 2,000 characters means no
  model call.
- The headless run uses `--setting-sources user --tools "" --no-session-persistence`, with
  `HARVEST_CHILD=1` in its environment so its own SessionEnd doesn't harvest again.

## Manual run and overrides

    python3 scripts/harvest.py ROOT SESSION_ID TRANSCRIPT

`HARVEST_DIR` overrides the inbox folder, and `HARVEST_CLAUDE` the `claude` binary (point it at
a stub that saves its stdin to look at the prompt without calling a model).

## Tests

    python3 -m unittest discover -s tests
