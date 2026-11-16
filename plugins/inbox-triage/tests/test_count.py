import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import count  # noqa: E402

INBOX = """## 2026-10-14 21:22, session f6f17a57

- [lesson][tab5] One. **Why:** a.
- [decision][any] Two. **Why:** b.

## 2026-10-16 09:50, session f6f17a57

- [result][tab5] Three. **Why:** c.
"""


class CountTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, ".claude"))

    def tearDown(self):
        self.tmp.cleanup()

    def config(self, **c):
        with open(os.path.join(self.root, ".claude", "harvest.json"), "w") as f:
            json.dump(dict({"project": "Probe"}, **c), f)

    def inbox(self, text, folder="behind_the_scenes"):
        os.makedirs(os.path.join(self.root, folder), exist_ok=True)
        with open(os.path.join(self.root, folder, "inbox.md"), "w") as f:
            f.write(text)

    def hook(self, env=None):
        out = io.StringIO()
        stdin = io.StringIO(json.dumps({"session_id": "s", "cwd": self.root}))
        old, sys.stdout = sys.stdout, out
        try:
            self.assertEqual(count.main(["count.py", "--hook"], stdin=stdin, env=env or {}), 0)
        finally:
            sys.stdout = old
        return out.getvalue()

    def test_counts_entries_not_headers(self):
        self.config()
        self.inbox(INBOX)
        text = self.hook()
        self.assertTrue(text.startswith("3 harvested entries wait in behind_the_scenes/inbox.md."))
        self.assertIn("inbox-triage:triage", text)

    def test_one_entry_is_singular(self):
        self.config()
        self.inbox("- [lesson][any] One. **Why:** a.\n")
        self.assertTrue(self.hook().startswith("1 harvested entry waits"))

    def test_configured_dir(self):
        self.config(dir="notes/private")
        self.inbox(INBOX, folder="notes/private")
        self.assertIn("in notes/private/inbox.md", self.hook())

    def test_silent_without_config(self):
        self.inbox(INBOX)
        self.assertEqual(self.hook(), "")

    def test_silent_when_empty_or_missing(self):
        self.config()
        self.assertEqual(self.hook(), "")
        self.inbox("")
        self.assertEqual(self.hook(), "")

    def test_project_dir_env_wins_over_cwd(self):
        self.config()
        self.inbox(INBOX)
        with tempfile.TemporaryDirectory() as other:
            out = io.StringIO()
            stdin = io.StringIO(json.dumps({"cwd": other}))
            old, sys.stdout = sys.stdout, out
            try:
                count.main(["count.py", "--hook"], stdin=stdin, env={"CLAUDE_PROJECT_DIR": self.root})
            finally:
                sys.stdout = old
        self.assertIn("3 harvested", out.getvalue())

    def test_bad_input_is_ignored(self):
        self.assertEqual(count.main(["count.py", "--hook"], stdin=io.StringIO("nope"), env={}), 0)


if __name__ == "__main__":
    unittest.main()
