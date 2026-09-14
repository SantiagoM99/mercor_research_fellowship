import contextlib
import io
import json
import sys
import tempfile
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import numeric_intervention as experiment
import judge_pilot as pilot


class InterventionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/"runs"
        with contextlib.redirect_stdout(io.StringIO()): experiment.prepare(self.root)
        self.directory=self.root/"qwen3-4b"
        self.manifest,self.plan=pilot.load_run(self.directory)

    def tearDown(self): self.temp.cleanup()

    def test_signed_intervals_and_endpoints(self):
        self.assertEqual(experiment.bounds('acceptable range is - 29 to - 27).'),[Decimal('-29'),Decimal('-27')])
        self.assertEqual(experiment.bounds('acceptable range is 4.671% to 4.765%'),[Decimal('4.671'),Decimal('4.765')])
        for row in self.plan:
            self.assertEqual(row['expected_from_design'],int(row['variant'] not in ['below','above']))

    def test_new_tasks_balanced_arms_and_identical_plans(self):
        self.assertEqual(len(self.plan),180)
        self.assertEqual({r['task_id'] for r in self.plan},{'145','1122','2205'})
        self.assertFalse(set(self.manifest['earlier_task_ids']) & {r['task_id'] for r in self.plan})
        self.assertEqual(Counter((r['arm'],r['language']) for r in self.plan),
            {('original','en'):45,('original','es'):45,('clarified','en'):45,('clarified','es'):45})
        other,_=pilot.load_run(self.root/'gemma3-4b')
        self.assertEqual(other['requests_sha256'],self.manifest['requests_sha256'])

    def test_only_amendment_changes_and_no_design_labels_are_sent(self):
        lookup={(r['stimulus_id'],r['language'],r['arm'],r['repeat']):r for r in self.plan}
        for row in self.plan:
            body=json.dumps(pilot.request_body(row['prompt'],self.manifest))
            self.assertNotIn('expected_from_design',body)
            self.assertNotIn('stimulus_id',body)
            if row['arm']=='original':
                other=lookup[(row['stimulus_id'],row['language'],'clarified',row['repeat'])]
                self.assertEqual(other['prompt'],row['prompt']+'\n\n'+self.manifest['amendment'])
                self.assertEqual(other['response'],row['response'])

    def write(self,label):
        events=[dict(request_id=r['request_id'],status='ok',result=label(r),
            plan_sha256=self.manifest['requests_sha256']) for r in self.plan]
        (self.directory/'results.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))

    def test_repairs_and_regressions_are_counted_in_both_directions(self):
        for improved in [True,False]:
            gold_arm='clarified' if improved else 'original'
            self.write(lambda r:r['expected_from_design'] if r['arm']==gold_arm else 1)
            with contextlib.redirect_stdout(io.StringIO()): data=experiment.metrics(self.directory)
            self.assertEqual(sum(c['repaired'] for c in data['paired_changes']),12 if improved else 0)
            self.assertEqual(sum(c['regressed'] for c in data['paired_changes']),0 if improved else 12)

    def test_missing_outputs_do_not_become_failures(self):
        with contextlib.redirect_stdout(io.StringIO()): data=experiment.metrics(self.directory)
        self.assertEqual(data['valid'],0)
        self.assertEqual(data['paired_changes'],[])
        self.assertTrue(all(r['error_rate'] is None for r in data['rates']))


if __name__=='__main__': unittest.main()
