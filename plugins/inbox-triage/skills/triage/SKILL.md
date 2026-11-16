---
name: triage
description: Sort the harvested inbox (behind_the_scenes/inbox.md or the folder .claude/harvest.json names) into the project's lessons, decisions and results files, with the user deciding each entry. Use when a session-start note says harvested entries are waiting, or when the user asks to sort, triage, go through or promote the inbox, the harvest, or the harvested lessons.
---

# Sort the harvested inbox

The `harvest` plugin appends entries to `<dir>/inbox.md` at the end of each session, where
`<dir>` is `dir` in `.claude/harvest.json` (default `behind_the_scenes`). The inbox looks like
this:

    ## 2026-10-14 21:22, session f6f17a57

    - [lesson][tab5] One or two sentences. **Why:** one line.
    - [decision][any] ...

Each entry is `- [KIND][TAG] text`. KIND and TAG are the ones the config lists.

## Where entries go

Read `destinations` in `.claude/harvest.json` first. If it isn't there, use the project's
`CLAUDE.md` (look for a rule on where notes, lessons or decisions go). If neither says, ask the
user once for the mapping and offer to write it into `destinations`.

## Steps

1. Read the inbox, the config, and the head and a few entries of every destination file, so
   promoted entries match each file's style: heading or table row, tag placement, numbering.
2. Say how many entries there are and how many sessions they come from. Ask whether to go through
   all of them or only some tags or kinds.
3. Go through them in small batches, grouped by destination file. For each entry, propose one of:
   - **promote**: the exact text you would add and the file it goes into, rewritten in that
     file's style, keeping its tag;
   - **merge**: the existing entry it belongs in, and the sentence you would add to it;
   - **drop**: why (already recorded, too vague, a one-off, not true any more).
   Point out duplicates within the inbox, and entries that a later entry contradicts.
4. **Nothing is written into a destination without the user's yes.** The user can say yes to a
   whole batch, change an entry's wording or destination, or skip it. A skipped entry stays in
   the inbox.
5. After each batch, write what was approved. Then delete every promoted, merged or dropped
   entry from the inbox, and delete a `## ` session header once it has no entries left. Never
   rewrite entries that are still waiting.
6. Keep numbering consistent. Example: if decisions are numbered across several files, find the
   highest number in all of them before adding one.
7. If the project has a link check or doc test (for example in `make test`), run it after
   writing.

## Do not

- Promote anything that holds credentials, typed commands meant to stay private, or anything
  the inbox entry marks private.
- Edit history folders the project says are never edited after the fact.
- Touch `harvest-state.json`, `harvest.log`, `harvest-pending.txt` or `harvest.lock`: they
  belong to the harvest plugin.
