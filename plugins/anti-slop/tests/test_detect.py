import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import detect  # noqa: E402

CFG = detect.load_config()
HOOK = os.path.join(ROOT, "scripts", "detect.py")

PAD = (
    " The service reads a config file at startup and writes logs to the data folder. "
    "Restart it after changing the port so the new value takes effect. "
    "Logs rotate daily and old files are deleted after two weeks."
)

SLOP = [
    "No fluff, no filler, just results." + PAD + " It's not just a tool, it's a workflow.",
    "This isn't a bug, it's a design choice. Let's dive into the details of how it works." + PAD,
    "Whether you're a beginner or an expert, this guide has you covered. It's not about speed, but about clarity." + PAD,
    "Great question! Here's the thing: it's worth noting that the cache is seamless." + PAD,
]

CLEAN = [
    "The script reads the config file, validates the port, and starts the server. "
    "If the port is taken, it exits with an error and tells you which process holds it." + PAD,
    "I changed three files. The parser now handles empty lines, the tests cover the new case, "
    "and the README mentions the flag. Run the suite with pytest to confirm." + PAD,
    "There is no config file in the repo, so I created one with defaults." + PAD,
    "Use the `--no-cache` flag, not `--cache`, when testing." + PAD,
]


def run_hook(payload, env_extra=None):
    env = dict(os.environ, ANTISLOP_REWRITE="0")
    env.pop("ANTISLOP", None)
    env.pop("ANTISLOP_INNER", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, HOOK], input=json.dumps(payload),
                       capture_output=True, text=True, env=env, timeout=20)
    return p.returncode, p.stdout, p.stderr


class Detect(unittest.TestCase):
    def test_slop_triggers(self):
        for msg in SLOP:
            r = detect.analyze(msg, CFG)
            self.assertGreaterEqual(r["score"], CFG["settings"]["trigger_score"], msg)

    def test_clean_passes(self):
        for msg in CLEAN:
            r = detect.analyze(msg, CFG)
            self.assertLess(r["score"], CFG["settings"]["trigger_score"], (msg, r["flagged"]))

    def test_code_is_ignored(self):
        msg = "```\nprint('no fluff, no filler')\n```\n" + CLEAN[0]
        self.assertLess(detect.analyze(msg, CFG)["score"], 2)

    def test_short_replies_skipped(self):
        self.assertEqual(detect.analyze("No fluff, no filler.", CFG)["score"], 0)

    def test_em_dash_density(self):
        msg = ("The tool — fast — works — well. " * 4) + PAD
        r = detect.analyze(msg, CFG)
        self.assertTrue(r["notes"])


class Hook(unittest.TestCase):
    def test_blocks_slop(self):
        code, out, _ = run_hook({"last_assistant_message": SLOP[0]})
        self.assertEqual(code, 0)
        d = json.loads(out)
        self.assertEqual(d["decision"], "block")
        self.assertIn("Sentences to fix", d["reason"])

    def test_clean_silent(self):
        code, out, _ = run_hook({"last_assistant_message": CLEAN[0]})
        self.assertEqual((code, out), (0, ""))

    def test_loop_guard(self):
        code, out, _ = run_hook({"last_assistant_message": SLOP[0], "stop_hook_active": True})
        self.assertEqual((code, out), (0, ""))

    def test_kill_switch(self):
        code, out, _ = run_hook({"last_assistant_message": SLOP[0]}, {"ANTISLOP": "off"})
        self.assertEqual((code, out), (0, ""))

    def test_inner_guard(self):
        code, out, _ = run_hook({"last_assistant_message": SLOP[0]}, {"ANTISLOP_INNER": "1"})
        self.assertEqual((code, out), (0, ""))

    def test_bad_input_fails_open(self):
        p = subprocess.run([sys.executable, HOOK], input="not json", capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (0, ""))

    def test_rewriter_failure_fails_open(self):
        # nonexistent model binary path -> rewriter returns {}, hook still blocks with flagged list
        code, out, _ = run_hook({"last_assistant_message": SLOP[0]},
                                {"ANTISLOP_REWRITE": "1", "PATH": "/nonexistent"})
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["decision"], "block")


if __name__ == "__main__":
    unittest.main()
