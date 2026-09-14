import csv
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from measure_sensitivity import (
    finance_bounds, finance_values, flows, market_cases, score_finance, xnpv,
)


class SensitivityTests(unittest.TestCase):
    def test_present_value_against_analytic_one_year_case(self):
        cashflows = [(date(2025, 1, 1), -100), (date(2026, 1, 1), 110)]
        self.assertAlmostEqual(xnpv(0.10, cashflows), 0, places=10)

    def test_back_solved_finance_values_zero_the_cashflows(self):
        values = finance_values()
        self.assertAlmostEqual(xnpv(values[1] / 100, flows()), 0, places=5)
        for cid, rate in zip([6, 7, 8], [0.15, 0.20, 0.25]):
            self.assertAlmostEqual(xnpv(rate, flows(sale=values[cid] * 1e6)), 0, places=5)
        for cid, rate in zip([9, 10, 11], [0.15, 0.20, 0.25]):
            self.assertAlmostEqual(xnpv(rate, flows(profit=values[cid])), 0, places=5)

    def test_finance_reproduction_uses_published_ranges_including_negative_npv(self):
        with (ROOT / "data/apex-v1-extended/train.csv").open(newline="") as stream:
            task = next(row for row in csv.DictReader(stream) if row["Task ID"] == "2287")
        bounds = finance_bounds(json.loads(task["Rubric JSON"]))
        self.assertEqual(bounds[5], [-2.4, -2.2])
        self.assertEqual(bounds[6], [2.8, 3.0])
        self.assertEqual(sum(c["numeric_pass"] for c in score_finance(finance_values(), bounds)), 11)
        self.assertEqual(sum(c["numeric_pass"] for c in score_finance(finance_values(maintenance=0), bounds)), 0)

    def test_intermediate_rounding_changes_only_two_reported_outputs(self):
        with (ROOT / "data/apex-v1-extended/documents/1172/US Population Census by State.csv").open(newline="") as stream:
            cases = market_cases(list(csv.DictReader(stream)))
        base, early = cases["baseline"], cases["round_each_intermediate"]
        differences = {key: early[key] - base[key] for key in base if early[key] != base[key]}
        self.assertEqual(differences, {"tam_usd": 21, "sam_usd": 2})
        changed_omission = sum(cases["omit_dc"][key] != base[key] for key in base)
        self.assertEqual(changed_omission, 5)


if __name__ == "__main__":
    unittest.main()
