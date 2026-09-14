import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import judge_pilot as pilot
import ollama_backend as backend


class OllamaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name) / "qwen"
        args = argparse.Namespace(provider="ollama", output=str(self.directory), model="qwen3:1.7b",
                                  repeats=3, seed=20260912, thinking_budget=1024, max_output_tokens=512,
                                  base_url="http://127.0.0.1:11434", context_window=4096, thinking=False)
        with contextlib.redirect_stdout(io.StringIO()): pilot.prepare(args)

    def tearDown(self): self.temp.cleanup()

    def test_local_request_uses_schema_disables_thinking_and_never_sends_design_labels(self):
        manifest, plan = pilot.load_run(self.directory)
        body = pilot.request_body(plan[0]["prompt"], manifest)
        self.assertEqual(body["model"], "qwen3:1.7b")
        self.assertFalse(body["think"])
        self.assertFalse(body["stream"])
        self.assertEqual(body["options"]["num_ctx"], 4096)
        self.assertEqual(body["options"]["num_predict"], 512)
        self.assertEqual(body["format"]["properties"]["result"]["enum"], [0, 1])
        self.assertNotIn("expected_from_design", json.dumps(body))

    def test_parser_rejects_truncation_and_nonbinary_values(self):
        result = {"done": True, "done_reason": "stop", "message": {
            "role": "assistant", "content": '{"result": 0, "reason": "Test only"}'}}
        self.assertEqual(backend.parse(result, pilot.validate_result)["result"], 0)
        result["done_reason"] = "length"
        with self.assertRaises(ValueError): backend.parse(result, pilot.validate_result)
        result["done_reason"] = "stop"
        result["message"]["content"] = '{"result": true, "reason": "Test only"}'
        with self.assertRaises(ValueError): backend.parse(result, pilot.validate_result)

    def test_local_url_rejects_remote_hosts_and_credentials(self):
        for value in ["http://example.com:11434", "http://user:secret@localhost:11434", "http://127.0.0.1:11434/other", "http://127.0.0.1:11434?key=x"]:
            with self.subTest(url=value), self.assertRaises(ValueError): backend.local_url(value)
        self.assertEqual(backend.local_url("http://127.0.0.1:11434/"), "http://127.0.0.1:11434")

    def test_preflight_records_model_digest_and_template_identity(self):
        manifest, _ = pilot.load_run(self.directory)
        replies = [{"version": "test"}, {"models": [{"name": "qwen3:1.7b", "digest": "sha256:abc", "size": 10}]},
                   {"template": "test", "parameters": "fixed"}]
        with patch.object(backend, "fetch", side_effect=replies): runtime = backend.identity(manifest)
        self.assertEqual(runtime["model_digest"], "sha256:abc")
        self.assertEqual(len(runtime["model_details_sha256"]), 64)

    def test_run_needs_no_api_key_and_refuses_changed_model_on_resume(self):
        runtime = {"server_version": "test", "model_digest": "sha256:abc"}
        response = {"model": "qwen3:1.7b", "done": True, "done_reason": "stop",
                    "message": {"role": "assistant", "content": '{"result": 1, "reason": "Test only"}'},
                    "eval_count": 12, "prompt_eval_count": 100}
        args = argparse.Namespace(output=str(self.directory), max_calls=1, delay=0, timeout=60)
        with patch.object(backend, "identity", return_value=dict(runtime)), \
             patch.object(pilot, "get_key", side_effect=AssertionError("Ollama must not use an API key")), \
             patch.object(pilot, "urlopen", return_value=io.BytesIO(json.dumps(response).encode())), \
             contextlib.redirect_stdout(io.StringIO()): pilot.run(args)
        events = pilot.load_events(self.directory)
        self.assertEqual(events[0]["status"], "ok")
        self.assertEqual(events[0]["model_version"], "sha256:abc")
        with patch.object(backend, "identity", return_value={**runtime, "model_digest": "sha256:changed"}), \
             self.assertRaisesRegex(ValueError, "identity changed"):
            pilot.run(args)
        self.assertFalse((self.directory / ".running").exists())

    def test_summary_detects_configuration_changes(self):
        manifest, plan = pilot.load_run(self.directory)
        event = {"request_id": plan[0]["request_id"], "status": "ok", "result": 1,
                 "plan_sha256": manifest["requests_sha256"],
                 "configuration_sha256": pilot.sha(json.dumps(manifest, sort_keys=True).encode())}
        (self.directory / "results.jsonl").write_text(json.dumps(event)+"\n")
        manifest["temperature"] = .7
        (self.directory / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "configuration changed"): pilot.summarize(self.directory)


if __name__ == "__main__": unittest.main()
