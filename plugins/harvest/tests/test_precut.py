import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import precut  # noqa: E402


def user(text, meta=False):
    e = {"type": "user", "message": {"role": "user", "content": text}}
    if meta:
        e["isMeta"] = True
    return e


def assistant(*blocks):
    return {"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}}


def result(tool_id, content, error=False):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": content, "is_error": error}]}}


ENTRIES = [
    {"type": "permission-mode"},
    user("why does the board go silent after unplug?<system-reminder>noise</system-reminder>"),
    user("Base directory for this skill: ...", meta=True),
    assistant({"type": "thinking", "thinking": "secret reasoning"}),
    assistant({"type": "text", "text": "Checking the suspend bit."}),
    assistant({"type": "tool_use", "id": "t1", "name": "Bash",
               "input": {"command": "make build-fw", "description": "Build"}}),
    result("t1", "x" * 5000),
    assistant({"type": "tool_use", "id": "t2", "name": "Write",
               "input": {"file_path": "/r/a.c", "content": "int main(){}" * 500}}),
    assistant({"type": "tool_use", "id": "t3", "name": "Bash", "input": {"command": "ctest"}}),
    result("t3", "Exit code 1\n" + "\n".join(f"line {i}" for i in range(100)), error=True),
    result("t4", [{"type": "text", "text": "logcut: captures/x.log\nrange: whole file\nresets: 1\n" + "-" * 40 + "\nI (1) a: x"}]),
    {"type": "attachment", "attachment": {"x": "y" * 1000}},
]


def write_jsonl(path, entries):
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


class CutEntriesTest(unittest.TestCase):
    def setUp(self):
        self.text = "\n".join(precut.cut_entries(ENTRIES, ["logcut:"]))

    def test_keeps_user_and_assistant_text(self):
        self.assertIn("USER: why does the board go silent after unplug?", self.text)
        self.assertIn("ASSISTANT: Checking the suspend bit.", self.text)

    def test_drops_reminders_meta_thinking_attachments(self):
        for gone in ("noise", "Base directory", "secret reasoning", "yyyy"):
            self.assertNotIn(gone, self.text)

    def test_tool_calls_are_one_line(self):
        self.assertIn("CALL Bash: make build-fw", self.text)
        self.assertIn("CALL Write: /r/a.c", self.text)
        self.assertNotIn("int main", self.text)

    def test_successful_results_dropped_errors_tail_kept(self):
        self.assertNotIn("xxxxx", self.text)
        self.assertIn("ERROR:", self.text)
        self.assertIn("line 99", self.text)
        self.assertNotIn("line 69\n", self.text + "\n")
        self.assertIn("line 70", self.text)

    def test_prefixed_result_header_kept(self):
        self.assertIn("LOGCUT: logcut: captures/x.log", self.text)
        self.assertNotIn("I (1) a: x", self.text)

    def test_prefixed_result_dropped_without_prefixes(self):
        self.assertNotIn("captures/x.log", "\n".join(precut.cut_entries(ENTRIES)))


class OffsetsTest(unittest.TestCase):
    def test_incomplete_last_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.jsonl")
            write_jsonl(p, [user("first")])
            with open(p, "a") as f:
                f.write('{"type": "user", "message": {"role": "user", "content": "sec')
            entries, off = precut.read_new(p, 0)
            self.assertEqual(len(entries), 1)
            with open(p, "a") as f:
                f.write('ond"}}\n')
            entries, off2 = precut.read_new(p, off)
            self.assertEqual(entries[0]["message"]["content"], "second")
            self.assertEqual(off2, os.path.getsize(p))

    def test_precut_with_subagent_and_offsets(self):
        with tempfile.TemporaryDirectory() as d:
            main = os.path.join(d, "abc.jsonl")
            write_jsonl(main, [user("main question")])
            sub = os.path.join(d, "abc", "subagents")
            os.makedirs(sub)
            write_jsonl(os.path.join(sub, "agent-1.jsonl"), [assistant({"type": "text", "text": "bench says 250 KB/s"})])
            with open(os.path.join(sub, "agent-1.meta.json"), "w") as f:
                json.dump({"description": "Measure file copy"}, f)
            text, offs = precut.precut(main, {})
            self.assertIn("USER: main question", text)
            self.assertIn("=== SUBAGENT: Measure file copy ===", text)
            self.assertIn("bench says 250 KB/s", text)
            again, _ = precut.precut(main, offs)
            self.assertEqual(again, "")

    def test_cap_drops_oldest(self):
        with tempfile.TemporaryDirectory() as d:
            main = os.path.join(d, "abc.jsonl")
            write_jsonl(main, [user(f"message {i} " + "z" * 100) for i in range(100)])
            text, _ = precut.precut(main, {}, cap=2000)
            self.assertLessEqual(len(text), 2100)
            self.assertIn("message 99", text)
            self.assertNotIn("message 0 ", text)
            self.assertTrue(text.startswith("[cut:"))


if __name__ == "__main__":
    unittest.main()
