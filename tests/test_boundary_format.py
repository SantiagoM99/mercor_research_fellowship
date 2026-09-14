import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import boundary_format as study
from numeric_checker import check_numeric


class BoundaryFormatTests(unittest.TestCase):
    def setUp(self):
        config=json.loads((ROOT/'experiments/content-paraphrase-v1.json').read_text())
        config.update(notations=['decimal','scientific'])
        self.plan=study.make_plan(config)

    def test_duplicates_removed_and_formats_matched(self):
        self.assertEqual(len(self.plan),192)
        pairs={(r['task_id'],r['criterion_id'],r['value']) for r in self.plan}
        self.assertEqual(len(pairs),32)
        for p in pairs:
            rows=[r for r in self.plan if (r['task_id'],r['criterion_id'],r['value'])==p]
            self.assertEqual(len(rows),6)
            self.assertEqual(len({r['expected_from_design'] for r in rows}),1)

    def test_numeric_parser_does_not_use_expected_metadata(self):
        for r in self.plan:
            self.assertEqual(check_numeric(r['response'],r['bounds'],r['unit'])['verdict'],r['expected_from_design'])
        r=copy.deepcopy(self.plan[0]); r['value']='999999'; r['expected_from_design']=1-r['expected_from_design']
        self.assertNotEqual(check_numeric(r['response'],r['bounds'],r['unit'])['verdict'],r['expected_from_design'])

    def test_abstain_on_conflict_missing_and_wrong_units(self):
        for response in ('No estimate available.', 'The IRR is 17.9% or 18.1%.',
                         'The IRR is 17.9%. The IRR is 18.1%.', 'The IRR is 17.9.',
                         'The IRR is 17.9x.', 'The IRR is approximately 17.9%.'):
            self.assertIsNone(check_numeric(response,['17.8','18.0'],'%')['verdict'])
        self.assertEqual(check_numeric('The IRR is 1.79E+1%.',['17.8','18.0'],'%')['verdict'],1)
        self.assertEqual(check_numeric('The IRR is 18.1%.',['17.8','18.0'],'%')['verdict'],0)

    def test_always_pass_and_fail_are_not_accepted_as_correct(self):
        for constant in (0,1):
            result=study.analyze(self.plan,{r['request_id']:{'result':constant} for r in self.plan})
            self.assertGreater(result['errors'],0)
            self.assertEqual(result['changed_pairs'],0)
            self.assertEqual(result['unstable_cells'],0)
        self.assertFalse(study.analyze(self.plan,{})['complete'])


if __name__=='__main__': unittest.main()
