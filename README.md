# claude-plugins

Claude Code plugins, published as a plugin marketplace.

| Plugin | What it does |
|---|---|
| [anti-slop](plugins/anti-slop) | Catches common AI-writing tells in Claude's replies ("not just X, it's Y", stock phrases, em-dash overuse) and has them rewritten in plain wording. A Stop hook plus a `plain-writing` skill. |
| [behind-the-scenes](plugins/behind-the-scenes) | Turns a project's Claude Code session transcripts into a `behind_the_scenes/` folder: one raw transcript and one narrative summary per session, plus a README index. Re-running it only adds new sessions. |

## Install

Add the marketplace once:

    /plugin marketplace add cccr/claude-plugins

Then install what you want:

    /plugin install anti-slop@cccr-plugins
    /plugin install behind-the-scenes@cccr-plugins

Restart the session afterwards so hooks and skills load.

## Layout

    .claude-plugin/marketplace.json   marketplace manifest
    plugins/<name>/                   one folder per plugin

## License

anti-slop is MIT-licensed (see its LICENSE). Other plugins have no license yet.
