import json
import os
import stat
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import harvest  # noqa: E402

STUB = """#!/bin/sh
cat > "$STUB_DIR/prompt.txt"
echo "$@" > "$STUB_DIR/args.txt"
echo "$HARVEST_CHILD" > "$STUB_DIR/env.txt"
if [ -f "$STUB_DIR/fail" ]; then echo boom >&2; exit 3; fi
cat "$STUB_DIR/reply"
"""


def write_session(path, n=40):
    with open(path, "w") as f:
        for i in range(n):
            f.write(json.dumps({"type": "user", "message": {"role": "user",
                                "content": f"question {i}: why does the suspend bit stick? " + "q" * 60}}) + "\n")


class HarvestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.bts = os.path.join(d, "bts")
        self.root = os.path.join(d, "repo")
        os.makedirs(os.path.join(self.root, "docs"))
        os.makedirs(os.path.join(self.root, ".claude"))
        self.write_config()
        with open(os.path.join(self.root, "docs", "lessons.md"), "w") as f:
            f.write("# Lessons\n\n### A catch-all wired profile takes over the USB link [any]\n\nbody\n")
        with open(os.path.join(self.root, "docs", "decisions.md"), "w") as f:
            f.write("| # | Decision |\n|---|---|\n| 1 | **USB network adapter plus SSH** [any] | x |\n")
        self.transcript = os.path.join(d, "sess.jsonl")
        write_session(self.transcript)
        self.claude = os.path.join(d, "claude")
        with open(self.claude, "w") as f:
            f.write(STUB)
        os.chmod(self.claude, os.stat(self.claude).st_mode | stat.S_IEXEC)
        os.environ["STUB_DIR"] = d
        with open(os.path.join(d, "reply"), "w") as f:
            f.write("Some preamble the model should not have written.\n"
                    "- [lesson][idf] The DWC2 suspend bit stays set after unplug. **Why:** TinyUSB drops the event.\n")

    def tearDown(self):
        self.tmp.cleanup()

    def write_config(self, **over):
        config = {"project": "Probe, a test project", "known": ["docs/*.md"],
                  "tags": {"any": "anywhere", "idf": "any ESP-IDF chip"}}
        config.update(over)
        with open(os.path.join(self.root, ".claude", "harvest.json"), "w") as f:
            json.dump(config, f)

    def run_harvest(self):
        return harvest.run("81dd9cb6-9dff", self.transcript, self.bts, self.claude, self.root)

    def inbox(self):
        p = os.path.join(self.bts, "inbox.md")
        return open(p).read() if os.path.exists(p) else ""

    def test_appends_entries_and_advances_offset(self):
        self.assertEqual(self.run_harvest(), 0)
        text = self.inbox()
        self.assertIn("session 81dd9cb6", text)
        self.assertIn("- [lesson][idf] The DWC2 suspend bit", text)
        self.assertNotIn("preamble", text)
        self.assertEqual(open(os.path.join(self.tmp.name, "env.txt")).read().strip(), "1")
        prompt = open(os.path.join(self.tmp.name, "prompt.txt")).read()
        self.assertIn("A catch-all wired profile takes over the USB link", prompt)
        self.assertIn("USB network adapter plus SSH", prompt)
        self.assertIn("question 39", prompt)
        self.assertIn("session on Probe, a test project. Extract", prompt)
        self.assertIn("- idf: any ESP-IDF chip", prompt)
        self.assertIn("- decision: a choice made", prompt)
        self.assertNotIn("{{", prompt)
        self.assertEqual(open(os.path.join(self.tmp.name, "args.txt")).read().split()[-1], "sonnet")
        state = json.load(open(os.path.join(self.bts, "harvest-state.json")))
        self.assertEqual(state[os.path.abspath(self.transcript)], os.path.getsize(self.transcript))

    def test_second_run_does_not_repeat(self):
        self.run_harvest()
        os.remove(os.path.join(self.tmp.name, "prompt.txt"))
        self.assertEqual(self.run_harvest(), 0)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "prompt.txt")))
        self.assertEqual(self.inbox().count("## "), 1)

    def test_failure_keeps_offset_and_logs(self):
        open(os.path.join(self.tmp.name, "fail"), "w").close()
        self.assertEqual(self.run_harvest(), 1)
        self.assertFalse(os.path.exists(os.path.join(self.bts, "harvest-state.json")))
        self.assertIn("boom", open(os.path.join(self.bts, "harvest.log")).read())
        os.remove(os.path.join(self.tmp.name, "fail"))
        self.assertEqual(self.run_harvest(), 0)
        self.assertIn("DWC2", self.inbox())

    def test_none_reply_writes_nothing_but_advances(self):
        with open(os.path.join(self.tmp.name, "reply"), "w") as f:
            f.write("NONE\n")
        self.assertEqual(self.run_harvest(), 0)
        self.assertEqual(self.inbox(), "")
        self.assertTrue(os.path.exists(os.path.join(self.bts, "harvest-state.json")))

    def test_unknown_tag_is_dropped(self):
        with open(os.path.join(self.tmp.name, "reply"), "w") as f:
            f.write("- [lesson][tab5] Not a tag here. **Why:** x.\n- [lesson][any] Kept. **Why:** y.\n")
        self.assertEqual(self.run_harvest(), 0)
        self.assertNotIn("Not a tag", self.inbox())
        self.assertIn("- [lesson][any] Kept.", self.inbox())

    def test_model_comes_from_config(self):
        self.write_config(model="haiku")
        self.run_harvest()
        self.assertEqual(open(os.path.join(self.tmp.name, "args.txt")).read().split()[-1], "haiku")

    def test_no_config_does_nothing(self):
        os.remove(os.path.join(self.root, ".claude", "harvest.json"))
        self.assertEqual(self.run_harvest(), 0)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "prompt.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.bts, "harvest-state.json")))

    def test_small_session_skips_model(self):
        write_session(self.transcript, n=2)
        self.assertEqual(self.run_harvest(), 0)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "prompt.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.bts, "harvest-state.json")))

    def other_session(self):
        path = os.path.join(self.tmp.name, "other.jsonl")
        write_session(path)
        return path

    def test_waits_for_a_held_lock(self):
        import threading
        os.makedirs(self.bts)
        lock = os.path.join(self.bts, "harvest.lock")
        open(lock, "w").close()
        threading.Timer(0.3, os.remove, [lock]).start()
        self.assertEqual(harvest.run("81dd9cb6-9dff", self.transcript, self.bts, self.claude,
                                     self.root, lock_wait=5), 0)
        self.assertIn("DWC2", self.inbox())

    def test_lock_timeout_queues_the_session_for_the_next_run(self):
        os.makedirs(self.bts)
        lock = os.path.join(self.bts, "harvest.lock")
        open(lock, "w").close()
        self.assertEqual(harvest.run("aaaaaaaa", self.transcript, self.bts, self.claude,
                                     self.root, lock_wait=0.2), 0)
        self.assertEqual(self.inbox(), "")
        os.remove(lock)
        self.assertEqual(harvest.run("bbbbbbbb", self.other_session(), self.bts, self.claude,
                                     self.root, lock_wait=0.2), 0)
        self.assertIn("session aaaaaaaa", self.inbox())
        self.assertIn("session bbbbbbbb", self.inbox())

    def test_failed_session_is_retried_with_the_next_session(self):
        open(os.path.join(self.tmp.name, "fail"), "w").close()
        self.assertEqual(harvest.run("aaaaaaaa", self.transcript, self.bts, self.claude, self.root), 1)
        os.remove(os.path.join(self.tmp.name, "fail"))
        self.assertEqual(harvest.run("bbbbbbbb", self.other_session(), self.bts, self.claude, self.root), 0)
        self.assertIn("session aaaaaaaa", self.inbox())
        self.assertIn("session bbbbbbbb", self.inbox())
        harvest.run("cccccccc", self.other_session(), self.bts, self.claude, self.root)
        self.assertEqual(self.inbox().count("session aaaaaaaa"), 1)

    def test_stale_lock_is_taken(self):
        os.makedirs(self.bts)
        lock = os.path.join(self.bts, "harvest.lock")
        open(lock, "w").close()
        old = time.time() - 31 * 60
        os.utime(lock, (old, old))
        self.assertEqual(self.run_harvest(), 0)
        self.assertIn("DWC2", self.inbox())
        self.assertFalse(os.path.exists(lock))


class HookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, ".claude"))
        with open(os.path.join(self.root, ".claude", "harvest.json"), "w") as f:
            json.dump({"project": "Probe"}, f)

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self, cwd="/elsewhere"):
        return json.dumps({"session_id": "s1", "transcript_path": "/t/s1.jsonl", "cwd": cwd})

    def test_spawns_with_root_session_and_transcript(self):
        calls = []
        rc = harvest.hook(self.payload(), spawn=calls.append, env={"CLAUDE_PROJECT_DIR": self.root})
        self.assertEqual(rc, 0)
        self.assertEqual(calls[0][-3:], [self.root, "s1", "/t/s1.jsonl"])

    def test_root_falls_back_to_cwd(self):
        calls = []
        harvest.hook(self.payload(cwd=self.root), spawn=calls.append, env={})
        self.assertEqual(calls[0][-3], self.root)

    def test_project_without_config_is_skipped(self):
        calls = []
        harvest.hook(self.payload(cwd=os.path.join(self.root, ".claude")), spawn=calls.append, env={})
        self.assertEqual(calls, [])

    def test_guard_env_stops_recursion(self):
        calls = []
        harvest.hook(self.payload(), spawn=calls.append,
                     env={"CLAUDE_PROJECT_DIR": self.root, "HARVEST_CHILD": "1"})
        self.assertEqual(calls, [])

    def test_bad_input_is_ignored(self):
        calls = []
        self.assertEqual(harvest.hook("not json", spawn=calls.append, env={}), 0)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
