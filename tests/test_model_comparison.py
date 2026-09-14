import contextlib
import io
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import model_comparison as comparison
import judge_pilot as pilot


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "runs"
        with contextlib.redirect_stdout(io.StringIO()):
            comparison.prepare(root=self.root)
        self.directory = self.root / "qwen3-1.7b"
        self.manifest, self.plan = pilot.load_run(self.directory)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_models_receive_identical_blinded_requests(self):
        plans = [pilot.load_run(d) for d in self.root.iterdir()]
        self.assertEqual(len({m["requests_sha256"] for m, _ in plans}), 1)
        self.assertEqual(len(self.plan), 270)
        probes = [r for r in self.plan if r["experiment"] == "numeric_probe"]
        self.assertEqual(Counter(r["language"] for r in probes), dict(en=54, es=54, pt=54))
        self.assertEqual({r["task_id"] for r in probes}, {"1172", "2287", "2145"})
        for r in self.plan:
            body = json.dumps(pilot.request_body(r["prompt"], self.manifest))
            for forbidden in ["expected_from_design", "accepted_bounds", "numeric_probe"]:
                self.assertNotIn(forbidden, body)

    def test_boundaries_and_negative_values_have_correct_design_labels(self):
        probes = [r for r in self.plan if r["experiment"] == "numeric_probe"]
        for r in probes:
            if r["variant"] in {"nominal", "valid_edge"}:
                self.assertEqual(r["expected_from_design"], 1)
            else:
                self.assertEqual(r["expected_from_design"], 0)
            self.assertIn(r["value"], r["response"])
        self.assertEqual({r["value"] for r in probes if r["task_id"] == "2287" and r["criterion_id"] == 5},
                         {"-2.3", "-2.4", "-2.5"})

    def write_results(self, selector, label):
        events = [{"request_id": r["request_id"], "status": "ok", "result": label(r),
                   "plan_sha256": self.manifest["requests_sha256"]} for r in self.plan if selector(r)]
        (self.directory / "results.jsonl").write_text("".join(json.dumps(e)+"\n" for e in events))

    def test_perfect_reference_has_no_errors_and_no_language_gaps(self):
        self.write_results(lambda r: True, lambda r: r["expected_from_design"])
        with contextlib.redirect_stdout(io.StringIO()): result = comparison.metrics(self.directory)
        self.assertEqual(result["valid"], 270)
        self.assertTrue(all(r["false_accept_rate"] == 0 and r["false_reject_rate"] == 0 for r in result["rates"]))
        self.assertTrue(all(c["other_minus_en"] == 0 for c in result["contrasts"]))
        self.assertEqual(Counter(c["language"] for c in result["contrasts"]), dict(es=36, pt=18))

    def test_unconditional_acceptance_is_agreement_but_not_correctness(self):
        self.write_results(lambda r: True, lambda r: 1)
        with contextlib.redirect_stdout(io.StringIO()): result = comparison.metrics(self.directory)
        self.assertTrue(all(r["false_accept_rate"] == 1 for r in result["rates"]))
        self.assertTrue(all(c["cross_language_disagreement"] == 0 for c in result["contrasts"]))

    def test_incomplete_language_is_missing_not_a_negative(self):
        self.write_results(lambda r: r["language"] == "en", lambda r: 1)
        with contextlib.redirect_stdout(io.StringIO()): result = comparison.metrics(self.directory)
        self.assertEqual(result["contrasts"], [])
        for rate in result["rates"]:
            if rate["language"] != "en":
                self.assertIsNone(rate["false_accept_rate"])
                self.assertIsNone(rate["false_reject_rate"])

    def test_opposite_pair_effects_do_not_disappear_when_aggregate_errors_match(self):
        def label(row):
            if row["pair_id"] == "1172-numeric-c2-outside":
                return int(row["language"] == "en")
            if row["pair_id"] == "2287-numeric-c5-outside":
                return int(row["language"] == "es")
            return row["expected_from_design"]
        self.write_results(lambda r: True,label)
        with contextlib.redirect_stdout(io.StringIO()): result=comparison.metrics(self.directory)
        rates={r["language"]:r for r in result["rates"] if r["experiment"]=="numeric_probe"}
        self.assertEqual(rates["en"]["false_accepts"],rates["es"]["false_accepts"])
        differences=[c["other_minus_en"] for c in result["contrasts"]
                     if c["experiment"]=="numeric_probe" and c["language"]=="es" and c["other_minus_en"]]
        self.assertEqual(sorted(differences),[-1,1])


if __name__ == "__main__":
    unittest.main()
