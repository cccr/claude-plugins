# claude-plugins

cccr's Claude Code plugins, published as a plugin marketplace. Each plugin lives in its own folder
under `plugins/` and shares no code with the others.

| Plugin | What it does |
|---|---|
| [anti-slop](plugins/anti-slop/) | Catches common AI-writing tells in Claude's replies ("not just X, it's Y", stock phrases, em-dash overuse) and has them rewritten in plain wording. A Stop hook plus a `plain-writing` skill. |
| [behind-the-scenes](plugins/behind-the-scenes/) | Turns a project's Claude Code session transcripts into a `behind_the_scenes/` folder: one raw transcript and one narrative summary per session, plus a README index. Re-running it only adds new sessions. |
| [harvest](plugins/harvest/) | At the end of each session (and before a compaction), a headless Claude reads the new part of the transcript and appends lessons, decisions and results to a private inbox. |
| [inbox-triage](plugins/inbox-triage/) | Says at session start how many harvested entries are waiting, and its `triage` skill sorts them into the project's docs, with you deciding each one. |

`harvest` and `inbox-triage` share one per-project file, `.claude/harvest.json`. A project
without it is left alone, so both plugins can stay enabled at user level everywhere.

## Install

Add the marketplace once:

    /plugin marketplace add cccr/claude-plugins

Then install what you want:

    /plugin install anti-slop@cccr
    /plugin install behind-the-scenes@cccr
    /plugin install harvest@cccr
    /plugin install inbox-triage@cccr

Restart the session afterwards so hooks and skills load. To pick up a new version:
`/plugin marketplace update cccr`.

## Work on it

- `make test` runs every plugin's `tests/` with `unittest`.
- `make validate` checks the manifests (`claude plugin validate .`).
- Try a plugin without installing it: `claude --plugin-dir plugins/<name>`.

## Add a plugin

1. `plugins/<name>/.claude-plugin/plugin.json` (name, version, description), plus whatever it
   ships: `skills/<skill>/SKILL.md`, `hooks/hooks.json` (paths via `${CLAUDE_PLUGIN_ROOT}`),
   `scripts/`, `tests/`, and a `README.md`.
2. An entry in `.claude-plugin/marketplace.json` with `"source": "./plugins/<name>"`.
3. `make test validate`.

Bump `version` in both `plugin.json` and `marketplace.json` when a plugin changes, so installed
copies update.

## License

anti-slop is MIT-licensed (see its LICENSE). The other plugins have no license yet.
