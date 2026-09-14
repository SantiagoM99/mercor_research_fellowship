#!/usr/bin/env python3
"""Report frozen boundary runs, retaining missing verdicts and complete-pair counts."""
from collections import defaultdict
import json
from pathlib import Path
from statistics import mean

import boundary_format as study
import judge_pilot as pilot

ROOT=study.ROOT


def summarize(directory):
    manifest,plan=pilot.load_run(directory)
    events=pilot.load_events(directory)
    ids={r['request_id'] for r in plan}
    for event in events:
        if event['request_id'] not in ids or event['plan_sha256']!=manifest['requests_sha256']:
            raise ValueError('Event does not match frozen requests')
        if event['configuration_sha256']!=pilot.sha(json.dumps(manifest,sort_keys=True).encode()):
            raise ValueError('Event configuration changed')
    done=pilot.successes(events)
    cells=study.analyze(plan,done)['cells']
    pairs=[]
    by_pair=defaultdict(dict)
    for c in cells: by_pair[(c['task_id'],c['criterion_id'],c['value'])][c['notation']]=c
    for key,formats in sorted(by_pair.items()):
        a,b=formats['decimal'],formats['scientific']
        complete=a['majority'] is not None and b['majority'] is not None
        pairs.append(dict(task_id=key[0],criterion_id=key[1],value=key[2],complete=complete,
            changed=int(a['majority']!=b['majority']) if complete else None,
            decimal_verdict=a['majority'],scientific_verdict=b['majority'],
            expected=a['expected_from_design'],
            repeat_disagreement=(a['repeat_disagreement']+b['repeat_disagreement'])/2 if complete else None))
    def aggregate(selected):
        valid=sum(c['valid'] for c in selected);planned=sum(c['planned'] for c in selected)
        errors=sum(c['errors'] for c in selected)
        pos=[c for c in selected if c['expected_from_design']==1];neg=[c for c in selected if c['expected_from_design']==0]
        return dict(planned=planned,valid=valid,unresolved=planned-valid,errors=errors,
            error_rate_on_valid=errors/valid if valid else None,
            planned_error_range=[errors/planned,(errors+planned-valid)/planned] if planned else None,
            false_approvals=sum(c['passes'] for c in neg),unmet_valid=sum(c['valid'] for c in neg),
            false_rejections=sum(c['valid']-c['passes'] for c in pos),met_valid=sum(c['valid'] for c in pos))
    conditions=[]
    for notation in ['decimal','scientific']:
        subset=[c for c in cells if c['notation']==notation]
        conditions.append(dict(notation=notation,**aggregate(subset)))
    nominal=[c for c in cells if 'nominal' in c['roles']]
    boundary=[c for c in cells if c['expected_from_design']==1 and 'nominal' not in c['roles']]
    family=[]
    for task in sorted({c['task_id'] for c in cells}):
        selected=[c for c in cells if c['task_id']==task]
        family.append(dict(task_id=task,**aggregate(selected)))
    contrasts=[]
    for task in sorted({c['task_id'] for c in cells}):
        a=aggregate([c for c in nominal if c['task_id']==task])
        b=aggregate([c for c in boundary if c['task_id']==task])
        contrasts.append(dict(task_id=task,nominal=a,boundary_excluding_nominal=b,
            difference_range=[b['planned_error_range'][0]-a['planned_error_range'][1],
                              b['planned_error_range'][1]-a['planned_error_range'][0]]))
    auto=[c for c in cells if c['checker']['verdict'] is not None]
    complete_pairs=[p for p in pairs if p['complete']]
    result=dict(model=manifest['model'],**aggregate(cells),attempts=len(events),
        failed_attempts=sum(e['status']!='ok' for e in events),conditions=conditions,
        nominal=aggregate(nominal),boundary_excluding_nominal=aggregate(boundary),
        boundary_role_overlap='Coincident nominal/inside values deduplicated and excluded from boundary-versus-nominal contrast.',
        equal_family_error_on_valid=mean(f['error_rate_on_valid'] for f in family) if all(f['valid'] for f in family) else None,
        families=family,cells=cells,pairs=pairs,complete_pairs=len(complete_pairs),planned_pairs=len(pairs),
        boundary_contrast_by_family=contrasts,
        equal_family_boundary_minus_nominal_range=[mean(c['difference_range'][i] for c in contrasts) for i in (0,1)],
        changed_pairs=sum(p['changed'] for p in complete_pairs),
        complete_cells=sum(c['majority'] is not None for c in cells),
        unstable_cells=sum(c['unstable'] is True for c in cells),
        repeat_disagreement_on_complete_pairs=mean(p['repeat_disagreement'] for p in complete_pairs) if complete_pairs else None,
        checker_automated_cells=len(auto),checker_cells=len(cells),
        checker_errors=sum(c['checker']['verdict']!=c['expected_from_design'] for c in auto))
    return result


def main():
    models=[summarize(study.RUNS/model) for model in ['qwen3-4b','gemma3-4b']]
    result=dict(study_id='boundary-format-v1',generated_utc=pilot.now(),models=models,
        report_code_sha256=pilot.sha(Path(__file__).read_bytes()),
        limitation='Three selected public task families; constructed English controls; local models only. Missing outputs are not wrong labels; valid-only rates may be selected. Incomplete pairs are excluded and counted. No H4/H6 reference-judge claim.')
    (ROOT/'analysis/boundary-format-v1.json').write_text(json.dumps(result,indent=2)+'\n')
    for model in models:
        path=study.RUNS/model['model'].replace(':','-')/'summary.json'
        path.write_text(json.dumps(model,indent=2)+'\n')
    print(json.dumps([{k:m[k] for k in ['model','planned','valid','errors','unresolved','failed_attempts','changed_pairs','complete_pairs','unstable_cells','checker_automated_cells','checker_errors']} for m in models],indent=2))


if __name__=='__main__':main()
