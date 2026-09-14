#!/usr/bin/env python3
"""Paired context controls: a number and unit do not identify the requested quantity."""
import json
from pathlib import Path

from boundary_format import UNITS
from numeric_checker import check_numeric
import judge_pilot as pilot

ROOT=Path(__file__).resolve().parents[1]
config=json.loads((ROOT/'experiments/boundary-format-v1.json').read_text())
controls=[]
for p in config['probes']:
    original=p['responses']['en'].format(value=p['values']['correct'])
    if p['task_id']=='145': target,replacement='Fixed Price','Performance Based'
    elif p['task_id']=='1122': target,replacement='Gen Z','Millennials'
    else: target,replacement='KatNip','AnotherCo'
    assert target in original
    changed=original.replace(target,replacement)
    pair=[]
    for response,expected in [(original,1),(changed,0)]:
        pair.append(dict(response=response,expected_from_design=expected,
            result=check_numeric(response,p['bounds'],UNITS[(p['task_id'],p['criterion_id'])])))
    controls.append(dict(task_id=p['task_id'],criterion_id=p['criterion_id'],criterion=p['rubrics']['en']['original'],pair=pair))
output=dict(study_id='boundary-format-v1-extraction-scope',generated_utc=pilot.now(),
    code_sha256=pilot.sha((ROOT/'scripts/numeric_checker.py').read_bytes()),pairs=controls,
    correct_controls_approved=sum(c['pair'][0]['result']['verdict']==1 for c in controls),
    wrong_target_controls_approved=sum(c['pair'][1]['result']['verdict']==1 for c in controls),
    pair_count=len(controls),limitation='Constructed context controls, not expert gold or natural responses. Confirms that the restricted numeric parser is not a complete rubric grader.')
(ROOT/'analysis/extraction-scope-v1.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps({k:output[k] for k in ['correct_controls_approved','wrong_target_controls_approved','pair_count','limitation']},indent=2))
