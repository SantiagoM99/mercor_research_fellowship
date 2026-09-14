#!/usr/bin/env python3
"""Offline engineering controls for the frozen restricted numeric extractor."""
import json
from pathlib import Path

from numeric_checker import check_numeric
from boundary_format import UNITS
import judge_pilot as pilot

ROOT=Path(__file__).resolve().parents[1]
config=json.loads((ROOT/'experiments/boundary-format-v1.json').read_text())
controls=[]
for p in config['probes']:
    unit=UNITS[(p['task_id'],p['criterion_id'])]
    correct=p['responses']['en'].format(value=p['values']['correct'])
    incorrect=p['responses']['en'].format(value=p['values']['incorrect'])
    responses={
        'missing':'No numerical estimate is available.',
        'conflicting_claims':correct+' '+incorrect,
        'alternative_values':correct.rstrip('.')+' or '+p['values']['incorrect']+'.',
        'approximate':correct.replace(' is ',' is approximately '),
        'unsupported_unit':'The reported value is '+p['values']['correct']+' billion units.',
        'unevaluated_expression':correct.replace(p['values']['correct'],p['values']['correct']+' + 0'),
    }
    for kind,response in responses.items():
        outcome=check_numeric(response,p['bounds'],unit)
        controls.append(dict(task_id=p['task_id'],criterion_id=p['criterion_id'],kind=kind,
            response=response,expected_action='abstain',outcome=outcome,passed=outcome['verdict'] is None))
result=dict(study_id='boundary-format-v1-extraction-controls',generated_utc=pilot.now(),
    code_sha256=pilot.sha((ROOT/'scripts/numeric_checker.py').read_bytes()),
    controls=controls,total=len(controls),passed=sum(c['passed'] for c in controls),
    scope='Engineering controls on deliberately restricted syntax; not independent professional validation or H6 on natural responses.')
(ROOT/'analysis/extraction-controls-v1.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['total','passed','scope']},indent=2))
