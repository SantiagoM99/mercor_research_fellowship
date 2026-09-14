import contextlib
import copy
import csv
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import content_paraphrase as experiment
import judge_pilot as pilot


class ContentParaphraseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'runs'
        with contextlib.redirect_stdout(io.StringIO()):
            experiment.prepare(self.root)
        self.manifest, self.plan = pilot.load_run(self.root / 'qwen3-4b')

    def tearDown(self):
        self.temp.cleanup()

    def result(self, classifier):
        return experiment.analyze(self.plan, {r['request_id']: {'result': classifier(r)} for r in self.plan})

    def test_frozen_factorial_and_prompt_isolation(self):
        self.assertEqual(len(self.plan), 288)
        other, _ = pilot.load_run(self.root / 'gemma3-4b')
        self.assertEqual(other['requests_sha256'], self.manifest['requests_sha256'])
        result = self.result(lambda r: r['expected_from_design'])
        self.assertEqual(len(result['cells']), 96)
        self.assertTrue(all(c['valid'] == 3 for c in result['cells']))
        self.assertEqual(sum(p['kind'] == 'content' for p in result['pairs']), 48)
        for row in self.plan:
            body = json.dumps(pilot.request_body(row['prompt'], self.manifest))
            for forbidden in ['expected_from_design', 'request_id', 'state', 'paraphrase']:
                self.assertNotIn('"'+forbidden+'"', body)
            if row['grading_language'] == 'en' and row['wording'] == 'original':
                self.assertEqual(row['prompt'], pilot.TEMPLATE.read_text().format(
                    criterion_description=row['criterion'], solution=row['response']))

    def test_always_pass_is_stable_but_never_detects_correction(self):
        result = self.result(lambda r: 1)
        pairs = result['pairs']
        self.assertTrue(all(p['detected'] == 0 for p in pairs if p['kind'] == 'content'))
        self.assertTrue(all(p['changed'] == 0 for p in pairs))
        self.assertTrue(all(r['error_rate'] == .5 for r in result['rates']))

    def test_reversed_verdicts_do_not_count_as_detection(self):
        result = self.result(lambda r: 1-r['expected_from_design'])
        content = [p for p in result['pairs'] if p['kind'] == 'content']
        self.assertTrue(all(p['changed'] == 1 and p['detected'] == 0 and p['reversed'] == 1 for p in content))

    def test_equal_task_weighting_differs_from_pooling(self):
        result = self.result(lambda r: r['expected_from_design'] if r['task_id'] == '2287' else 1)
        macro = next(r for r in result['rates'] if r['task_id'] == 'equal_task_macro' and r['language'] == 'en')
        self.assertAlmostEqual(macro['content_rate'], 1/3)
        self.assertAlmostEqual(macro['content_count']/macro['content_pairs'], 2/3)

    def test_paraphrase_changes_have_direction_and_repeat_noise_is_separate(self):
        result = self.result(lambda r: r['expected_from_design'] if r['wording'] == 'original' else 1-r['expected_from_design'])
        para = [p for p in result['pairs'] if p['kind'] == 'paraphrase']
        self.assertTrue(all(p['regressed'] == 1 and p['repaired'] == 0 for p in para))
        noise = self.result(lambda r: int(r['repeat'] != 0))
        self.assertTrue(all(c['majority'] == 1 and c['unstable'] for c in noise['cells']))
        self.assertTrue(all(abs(c['within_disagreement']-2/3) < 1e-9 for c in noise['cells']))

    def test_missing_outputs_do_not_create_metrics(self):
        result = experiment.analyze(self.plan, {})
        self.assertEqual(result['pairs'], [])
        self.assertEqual(result['rates'], [])
        self.assertTrue(all(c['majority'] is None for c in result['cells']))

    def test_modified_numeric_translation_is_rejected(self):
        config = copy.deepcopy(self.manifest['study_config'])
        config['probes'][0]['rubrics']['es']['paraphrase'] += ' 10'
        with (ROOT/'data/apex-v1-extended/train.csv').open() as f:
            tasks = {r['Task ID']: r for r in csv.DictReader(f)}
        templates = {'en': pilot.TEMPLATE.read_text(), 'es': (ROOT/config['spanish_template']).read_text()}
        with self.assertRaisesRegex(ValueError, 'changed numbers'):
            experiment.records(config, tasks, templates)


if __name__ == '__main__':
    unittest.main()
