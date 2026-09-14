import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import judge_pilot as pilot


def response(result=1, finish="STOP"):
    return {"candidates": [{"finishReason": finish, "content": {"parts": [
        {"text": json.dumps({"result": result, "reason": "Test fixture only"})}]}}],
        "usageMetadata": {"totalTokenCount": 42}, "modelVersion": "test-only"}


class JudgePilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / "run"
        args = argparse.Namespace(output=str(self.directory), model="gemini-2.5-flash", repeats=3,
                                  seed=10, thinking_budget=1024, max_output_tokens=2048)
        with contextlib.redirect_stdout(io.StringIO()): pilot.prepare(args)

    def tearDown(self):
        self.temp.cleanup()

    def test_plan_balances_languages_and_keeps_design_labels_out_of_request(self):
        manifest, plan = pilot.load_run(self.directory)
        self.assertEqual(len(plan), 108)
        self.assertEqual(sum(r["language"] == "es" for r in plan), 54)
        body = pilot.request_body(plan[0]["prompt"], manifest)
        self.assertNotIn("expected_from_design", json.dumps(body))
        self.assertNotIn("pair_id", json.dumps(body))
        self.assertNotIn("request_id", json.dumps(body))

    def test_frozen_plan_detects_edits(self):
        path = self.directory / "requests.jsonl"
        path.write_text(path.read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "changed"): pilot.load_run(self.directory)

    def test_output_parser_rejects_nonbinary_and_truncated_outputs(self):
        for value in [True, "1", 2, None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                pilot.parse_response(response(value))
        with self.assertRaises(ValueError): pilot.parse_response(response(1, "MAX_TOKENS"))
        self.assertEqual(pilot.parse_response(response(0))["result"], 0)

    def test_empty_results_are_missing_not_failed(self):
        with contextlib.redirect_stdout(io.StringIO()): result = pilot.summarize(self.directory)
        self.assertEqual(result["valid"], 0)
        self.assertEqual(result["unresolved"], 108)
        self.assertTrue(all(c["pass_fraction"] is None for c in result["cells"]))

    def test_resume_only_calls_pending_requests_and_respects_attempt_limit(self):
        args = argparse.Namespace(output=str(self.directory), max_calls=2, delay=0)
        with patch.object(pilot, "get_key", return_value="test-key"), \
                patch.object(pilot, "urlopen", side_effect=lambda *a, **k: io.BytesIO(json.dumps(response()).encode())) as send, \
                contextlib.redirect_stdout(io.StringIO()):
            pilot.run(args); pilot.run(args)
        self.assertEqual(send.call_count, 4)
        self.assertEqual(len(pilot.successes(pilot.load_events(self.directory))), 4)
        self.assertFalse((self.directory / ".running").exists())

    def test_http_error_is_logged_without_body_and_stops(self):
        args = argparse.Namespace(output=str(self.directory), max_calls=12, delay=0)
        error = HTTPError("https://example.invalid", 429, "Too Many Requests", {}, io.BytesIO(b"private-error-body"))
        with patch.object(pilot, "get_key", return_value="test-key"), \
                patch.object(pilot, "urlopen", side_effect=error) as send, \
                contextlib.redirect_stdout(io.StringIO()):
            pilot.run(args); result = pilot.summarize(self.directory)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(result["valid"], 0)
        self.assertEqual(result["failed_attempts"], 1)
        self.assertNotIn("private-error-body", (self.directory / "results.jsonl").read_text())

    def test_language_contrast_uses_all_repeats_and_separates_instability(self):
        manifest, plan = pilot.load_run(self.directory)
        selected = [r for r in plan if r["pair_id"] == "1172-complete" and r["criterion_id"] == 1]
        events = [{"request_id": r["request_id"], "status": "ok", "result": int(r["language"] == "en"),
                   "plan_sha256": manifest["requests_sha256"]} for r in selected]
        (self.directory / "results.jsonl").write_text("".join(json.dumps(e)+"\n" for e in events))
        with contextlib.redirect_stdout(io.StringIO()): result = pilot.summarize(self.directory)
        contrast = result["complete_cell_contrasts"][0]
        self.assertEqual(contrast["es_minus_en"], -1)
        self.assertEqual(contrast["cross_language_disagreement_all_repeat_pairs"], 1)
        self.assertEqual(contrast["within_en_disagreement"], 0)
        self.assertEqual(contrast["within_es_disagreement"], 0)


if __name__ == "__main__":
    unittest.main()
