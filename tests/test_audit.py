import csv
import hashlib
import json
import sys
import unittest
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from audit_apex import audit, descendants
from build_pilot_fixture import calculate


class AuditTests(unittest.TestCase):
    def test_downloaded_files_match_provenance(self):
        for directory in ["apex-v1-extended", "apex-harness-reference"]:
            folder = ROOT / "data" / directory
            manifest = json.loads((folder / "manifest.json").read_text())
            for name, record in manifest["files"].items():
                with self.subTest(file=name):
                    local = record.get("local_file", name)
                    actual = hashlib.sha256((folder / local).read_bytes()).hexdigest()
                    self.assertEqual(actual, record["sha256"])

    def test_diamond_graph_counts_descendant_once(self):
        children = defaultdict(set, {1: {2, 3}, 2: {4}, 3: {4}})
        self.assertEqual(descendants(1, children), {2, 3, 4})
        self.assertEqual(descendants(4, children), set())

    def test_cycle_and_unknown_reference_are_reported(self):
        def criterion(deps):
            return {"dependent_criteria": deps, "criterion_type": ["Reasoning"], "weight": "Primary objective(s)"}
        row = {"Task ID": "1", "Domain": "Finance", "File Attachments": "",
               "Rubric JSON": json.dumps({"criterion 1": criterion([2]), "criterion 2": criterion([1, 99])})}
        summary, _, _ = audit([row])
        self.assertEqual(summary["dependency_cycles"][0]["criteria"], [1, 2])
        self.assertEqual(summary["invalid_dependency_references"][0]["reference"], 99)

    def test_verified_dataset_counts(self):
        with (ROOT / "data/apex-v1-extended/train.csv").open(newline="") as stream:
            summary, tasks, flat = audit(list(csv.DictReader(stream)))
        self.assertEqual((summary["tasks"], summary["criteria"], summary["dependent_criteria"]), (100, 1140, 541))
        self.assertEqual(summary["tasks_with_dependencies"], 93)
        nike = next(t for t in tasks if t["task_id"] == "2108")
        self.assertEqual((nike["max_reach_criterion"], nike["max_descendants"]), (1, 5))
        katnip = [c for c in flat if c["task_id"] == "2287"]
        self.assertEqual(len(katnip), 11)
        self.assertTrue(all(c["criterion_type_normalized"] == "Reasoning" for c in katnip))

    def test_projection_uses_state_growth_before_aggregation(self):
        # Equal initial populations, different growth; projecting the aggregate is wrong.
        rows = [{"2020": "100", "2024": "100"}, {"2020": "100", "2024": "200"}]
        rounded, raw = calculate(rows)
        self.assertEqual(rounded["population_2032"], 900)
        self.assertEqual(Decimal(raw["tam_usd"]), Decimal("6750"))
        self.assertNotEqual(rounded["population_2032"], 300 * (300 / 200) ** 2)

    def test_matched_fixture_is_not_presented_as_observed_data(self):
        fixture = json.loads((ROOT / "data/pilot/1172_matched_responses.json").read_text())
        self.assertEqual(fixture["status"], "constructed_stimuli_not_experimental_results")
        pairs = defaultdict(list)
        for case in fixture["cases"]:
            self.assertIsNone(case["model_judgments"])
            self.assertEqual(case["human_review_status"], "pending")
            pairs[case["pair_id"]].append(case)
        self.assertEqual(len(pairs), 3)
        for cases in pairs.values():
            self.assertEqual({c["language"] for c in cases}, {"en", "es"})
            self.assertEqual(cases[0]["expected_labels_from_fixture_design"], cases[1]["expected_labels_from_fixture_design"])


if __name__ == "__main__":
    unittest.main()
