import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import boundary_format as study
import judge_pilot as pilot
from report_boundary_format import summarize


class BoundaryReportTests(unittest.TestCase):
    def test_missing_verdict_is_neither_wrong_nor_a_complete_pair(self):
        config=json.loads((ROOT/'experiments/boundary-format-v1.json').read_text())
        plan=study.make_plan(config)
        missing=plan[0]['request_id']
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            payload=''.join(json.dumps(r)+'\n' for r in plan).encode()
            manifest=dict(model='test',planned_calls=len(plan),requests_sha256=pilot.sha(payload))
            (directory/'requests.jsonl').write_bytes(payload)
            (directory/'manifest.json').write_text(json.dumps(manifest))
            events=[dict(request_id=r['request_id'],result=r['expected_from_design'],status='ok',
                plan_sha256=manifest['requests_sha256'],configuration_sha256=pilot.sha(json.dumps(manifest,sort_keys=True).encode())) for r in plan if r['request_id']!=missing]
            (directory/'results.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            report=summarize(directory)
            self.assertEqual(report['valid'],191)
            self.assertEqual(report['errors'],0)
            self.assertEqual(report['unresolved'],1)
            self.assertEqual(report['complete_pairs'],31)
            self.assertEqual(report['changed_pairs'],0)
            self.assertEqual(report['planned_error_range'],[0,1/192])
            events[0]['configuration_sha256']='changed'
            (directory/'results.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            with self.assertRaisesRegex(ValueError,'configuration'):summarize(directory)

if __name__=='__main__':unittest.main()
