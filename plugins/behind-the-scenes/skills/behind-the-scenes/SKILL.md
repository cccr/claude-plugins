---
name: behind-the-scenes
description: Mine every locally-stored Claude Code session transcript tied to a project into a `behind_the_scenes/` folder inside that project — one paired raw-transcript + narrative-summary file per session, chronologically ordered, plus a README index. Built for "we did a lot of work here, help me write about it" moments — a postmortem, a changelog, an onboarding doc, or an article about how a project actually came together. Use this whenever the user asks to reconstruct, archive, dump, or save the history/context/journey behind a project or folder; asks what `/resume` or the project's session list contains; wants to turn past sessions into documentation; or asks "how did we get here" / "what have we actually done in this project" about work spanning multiple sessions. Safe to re-run on the same project later — it only processes sessions it hasn't already written up, so treat "update the behind_the_scenes folder" or "add anything new" as a trigger too, not just the first-time dump.
---

# behind-the-scenes

Turns the session transcripts Claude Code already keeps on disk
(`~/.claude/projects/<slug>/*.jsonl`) into a durable, human-readable record
that lives *in the project itself* — not in scratch space, not only in this
conversation's context. The point isn't to summarize once and move on; it's
to leave behind a folder a human (or a future Claude session) can actually
read, cite, and add to over time.

## Why this exists

Session transcripts are the most complete record of how a project actually
got built — every dead end, every correction, every "wait, that's not what I
meant." But they live in `~/.claude/projects/`, are named by opaque UUIDs,
get pruned/rotated over time, and are individually too large and noisy
(tool-call JSON, file payloads) to hand a human directly. This skill turns
that raw material into something durable and readable, sitting next to the
code it documents.

## Step 0 — locate every session that belongs to this project

**Find the project's own transcripts.** Take the project's absolute root
path (the user's cwd, or whatever directory they named) and compute its
slug the way Claude Code does: replace every `/` and `_` with `-`. Check for
a matching directory under `~/.claude/projects/`:

```bash
ls ~/.claude/projects/ | grep -i "$(basename /path/to/project)"
```

If the computed slug doesn't exist verbatim, this grep usually still finds
it (or something close) — confirm by peeking at one line of a candidate
`.jsonl` and checking it references the right files/paths before trusting
it. Don't guess silently; a wrong slug means silently returning nothing.

Once you have the right directory, triage what's there before reading
anything in full:

```bash
python3 <skill-dir>/scripts/extract_transcript.py scan ~/.claude/projects/<slug>
```

This lists every session's line count, time span, and first real user
message — enough to decide what's worth a full write-up without spending any
tokens on the heavy files yet. Sessions that are pure noise (a single
slash-command with no follow-through, a session that's only the
`<local-command-caveat>` wrapper, or — importantly — *the current session
itself*, which is naturally still tiny/incomplete while it's running) aren't
worth their own entry; use judgment, and when genuinely unsure whether
something's substantive, err toward including it rather than silently
dropping real work.

**Look for lost or predecessor sessions.** Projects get renamed, moved
between machines, or migrated across cloud drives — and `~/.claude/projects/`
keys entirely on absolute path, so a moved project leaves its old transcripts
orphaned under the *old* path's slug. Two things are worth checking:

1. `ls ~/.claude/projects/` for other directories sharing the project's
   basename or an old name mentioned in its docs/git history (e.g. a
   `CLAUDE.md` line about migrating to a new location, a `git remote`
   history, or the user just telling you it used to live somewhere else).
2. A directory that has a `memory/` subfolder but *no* `.jsonl` files — that
   pattern means the transcripts were pruned or lost but persistent memory
   notes written during those sessions survived. Read them; they're the only
   remaining first-hand record and deserve their own entry, clearly marked as
   reconstructed-from-memory rather than from a transcript.

If you find a plausible predecessor project but can't be sure it's the same
project's history rather than an unrelated one, ask the user rather than
silently including or excluding it — this is exactly the kind of ambiguous
call worth a quick confirmation.

## Step 1 — check what's already been written up

Look for an existing `behind_the_scenes/` folder in the project root. If one
exists, read its `README.md` (or scan the filenames) to see which session
files/IDs it already covers — each summary file's closing line should name
its source (see the template below), so this is a quick grep, not a full
read of every file. **Only process sessions not already covered.** This is
what makes the skill safe to re-run months later after a new burst of work:
it should extend the folder, not regenerate it. If literally everything is
already covered, say so and stop rather than doing busywork.

## Step 2 — process each new session in parallel

For every not-yet-covered session, spawn one subagent per session (in a
single message, so they run in parallel) with `subagent_type: general-purpose`
to produce both files at once. Each agent needs a **self-contained** prompt
(it starts with no context) that includes:

- The project's own `CLAUDE.md` or README path, if one exists, so the agent
  understands the domain/terminology before it starts reading.
- The full absolute path to the session's `.jsonl` file, its rough time span
  (from Step 0's scan), and the first user message, so the agent knows what
  it's walking into.
- Instructions to run the extraction script itself for the raw file, e.g.:

  ```bash
  python3 <skill-dir>/scripts/extract_transcript.py extract \
    <session>.jsonl <project>/behind_the_scenes/<NN-date-slug>.raw.md "<short title>"
  ```

  For a large session (roughly >500 lines / a few MB), tell the agent the
  file is too big to `Read` in one pass and to rely on the extracted `.raw.md`
  (or targeted `grep`/`python3` passes over the source) rather than trying to
  load the whole thing into its own context.
- Instructions to then write `<NN-date-slug>.summary.md`: a chronological
  narrative (not bullet fragments) that leads with **what the user was
  actually trying to accomplish and why** — the idea behind the ask, the
  problem it solved, the bigger thing it was in service of — not with the
  mechanics of what broke. A session exists because someone wanted something
  to work a certain way; that intention is the headline, and the bugs/fixes
  are supporting texture underneath it, not the other way around. Skip typos,
  minor corrections, and small technical missteps entirely unless one
  actually reveals something about the idea itself (e.g. a bug that forced a
  real design decision, or a dead end that changed the plan) — most don't,
  and listing them turns a narrative into a changelog. When something
  genuinely was a meaningful dead end or a hard-won fix, it's still worth
  keeping — the test is "does this teach the reader something about the
  project," not "did an error occur." Direct quotes that capture a real
  moment (especially ones that reveal *why* the user wanted something) are
  worth including; quotes that are just a bug report usually aren't. Close
  with the end state — what the intention turned into, not just what got
  fixed. Length should scale with the session's real size — a 30-minute
  session doesn't need 1000 words. Have the agent report the summary
  directly as its final message rather than writing it — you'll be the one
  to save it (see Step 3), so you can review before it lands on disk.
- A closing line specifying the exact output filename convention (below), so
  every agent picks consistent, sortable names.

**Naming convention:** `NN-YYYY-MM-DD-slug.raw.md` /
`NN-YYYY-MM-DD-slug.summary.md`, where `NN` continues the existing sequence
(zero-padded, two digits) and `slug` is a short kebab-case phrase capturing
the session's topic (3-5 words). A session with no transcript (the
memory-only case from Step 0) gets `.raw.md` containing the memory notes
verbatim instead of an extracted transcript, clearly labeled as such.

## Step 3 — write the files and the index

Once each agent reports back, write its summary to
`<project>/behind_the_scenes/<NN-date-slug>.summary.md` yourself (the raw
file is already on disk from the agent's own extraction step). End every
summary file with one line naming its source, e.g.:

```
---
Source: `<session-uuid>.jsonl` · <first_ts> → <last_ts>
```

This line is what Step 1 greps for on a future run, so don't skip it.

Then write (or update) `<project>/behind_the_scenes/README.md`: a short
table of every session — date, one-line description, filenames — newest or
oldest first, whichever reads more naturally for the project's actual
history. If updating an existing README, just append new rows; don't
rewrite entries that already exist.

## Step 4 — offer the polished version, don't default to it

The folder of raw + summary files is the actual deliverable — it's what
makes this durable and re-visitable. Building a single polished narrative (a
long-read compiling all sessions into one chronological story) is a
nice-to-have on top, not a required step: it costs real design effort and
isn't always what the user wants yet, especially on a first run with many
sessions. Offer it rather than assuming it — e.g. "want me to also compile
these into one narrative writeup?" — and if they say yes, use the
`artifact-design` skill for the visual design before building it, since it's
a genuine reading experience, not just a text dump.

**Save it as a file in `behind_the_scenes/` (e.g. `compiled-narrative.html`),
not as a hosted Claude Artifact, unless the user asks to share or publish
it.** The whole point of this skill is a durable, local, offline record —
publishing a hosted link works against that, and it's an extra upload of
what might be sensitive project history that the user hasn't asked to put
anywhere but their own disk. If it's an HTML page, make it a complete
standalone document (`<!doctype html>` through `</html>`, with its own
`<head>`/`<style>`) rather than a bare fragment, since there's no publishing
step here to wrap it for you — open it straight in a browser to check.

## Notes on judgment calls

- **This is about durability, not just this conversation.** Writing straight
  to the target project's own `behind_the_scenes/` folder (never to `/tmp` or
  a scratchpad) is the entire point — a future session, a teammate, or the
  user six months from now should be able to open the folder cold.
- **Raw files are for quotes, not full replay.** They deliberately collapse
  tool payloads to one-line previews. If someone needs the literal, complete
  API traffic, point them at the original `.jsonl` — don't try to reproduce
  it in full inside `behind_the_scenes/`.
- **A session with nothing interesting in it doesn't need an entry.** Use
  judgment on genuinely empty/noise sessions (per Step 0), but the bar should
  be low — a "boring" routine session is still real material for a postmortem
  about how much of the work was unglamorous upkeep.
- **This is a record of an idea, not a bug log.** It's easy to default to
  writing up whatever was easiest to notice in a transcript — errors, typos,
  regex gotchas — because they're concrete and quotable. Resist that. A
  reader (including the user, months later) wants to know what they were
  building and why it mattered; a wall of "then a bug was found and fixed"
  entries reads like a changelog and buries the actual story. Ask, for every
  paragraph: does this tell the reader something about the project's purpose
  or the thinking behind a decision? If not, it's probably a cut, even if
  it's the most dramatic thing that happened in the session.
