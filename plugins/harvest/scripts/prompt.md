You read the cut-down transcript of one Claude Code session on {{PROJECT}}. Extract what a
later session should not have to learn again.

Return only Markdown list items, one per line, nothing before or after them, in this form:

- [KIND][TAG] One or two plain sentences. **Why:** one line.

KIND is one of:
{{KINDS}}

TAG says how far it carries:
{{TAGS}}

Rules:
- Only what this transcript shows happened or was decided. No advice, no guesses.
- Skip anything already in the known entries below, even if worded differently.
- Never write shell commands typed on a device, passwords, keys, tokens, SSIDs with
  passphrases, or anything the session marked private.
- Fewer, sharper items beat many. Ten is a lot for one session.
- If there is nothing new, return exactly: NONE

Known entries:

{{KNOWN}}

Transcript:

{{TRANSCRIPT}}
