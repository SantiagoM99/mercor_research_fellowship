#!/usr/bin/env python3
"""Frozen local boundary/notation diagnostic; prepare and report are offline."""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import random
from statistics import mean
import tempfile

import content_paraphrase as source
import judge_pilot as pilot
from numeric_checker import check_numeric

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / 'runs/boundary-format-v1'
CONFIG = ROOT / 'experiments/boundary-format-v1.json'
UNITS = {('145', 2): '', ('1122', 1): '', ('2287', 1): '%',
         ('2287', 2): 'x', ('2287', 5): 'million dollars', ('2287', 3): 'million dollars'}


def make_plan(config):
    rows = []
    template = pilot.TEMPLATE.read_text()
    for p in config['probes']:
        lo, hi = map(Decimal, p['bounds'])
        nominal = Decimal(p['values']['correct'])
        step = Decimal(1).scaleb(nominal.as_tuple().exponent)
        positions = {'nominal': nominal, 'lower_endpoint': lo, 'upper_endpoint': hi,
                     'lower_inside': lo + step, 'upper_inside': hi - step,
                     'lower_outside': lo - step, 'upper_outside': hi + step}
        for vi, value in enumerate(sorted(set(positions.values()))):
            roles = sorted(k for k, v in positions.items() if v == value)
            for notation in config['notations']:
                displayed = format(value, 'f') if notation == 'decimal' else format(value, 'E')
                response = p['responses']['en'].format(value=displayed)
                criterion = p['rubrics']['en']['original']
                prompt = template.format(criterion_description=criterion, solution=response)
                cell = f"{p['task_id']}-c{p['criterion_id']}-v{vi}-{notation}"
                for repeat in range(config['repeats']):
                    rows.append(dict(request_id=f'{cell}:r{repeat}', pair_id=cell,
                        task_id=p['task_id'], criterion_id=p['criterion_id'], language='en',
                        repeat=repeat, value=str(value), roles=roles, notation=notation,
                        bounds=p['bounds'], unit=UNITS[(p['task_id'], p['criterion_id'])],
                        expected_from_design=int(lo <= value <= hi), criterion=criterion,
                        response=response, prompt=prompt, prompt_sha256=pilot.sha(prompt.encode())))
    random.Random(config['seed']).shuffle(rows)
    return rows


def prepare(root=RUNS):
    # Reuse the existing source-validation path; it checks source hashes and re-solves anchors.
    with tempfile.TemporaryDirectory() as tmp:
        source.prepare(Path(tmp) / 'source-validation')
        old, _ = pilot.load_run(Path(tmp) / 'source-validation/qwen3-4b')
    base = old['study_config']
    config = dict(study_id='boundary-format-v1', models=base['models'], repeats=3,
                  seed=20260913, notations=['decimal', 'scientific'], probes=base['probes'],
                  scope='English constructed controls on three previously inspected public families; not Mercor reference-judge evidence.',
                  protocol='DESIGN.md C4, recorded before execution; coincident boundary values deduplicated')
    rows = make_plan(config)
    assert len(rows) == 192 and len({r['request_id'] for r in rows}) == 192
    payload = ''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows).encode()
    directories = [Path(root)/m.replace(':', '-') for m in config['models']]
    if CONFIG.exists() or any(d.exists() for d in directories):
        raise ValueError('Frozen study already exists; do not overwrite it')
    config_bytes = (json.dumps(config, indent=2)+'\n').encode()
    CONFIG.write_bytes(config_bytes)
    for model, directory in zip(config['models'], directories):
        manifest = dict(schema_version=3, study_id=config['study_id'], created_utc=pilot.now(),
            provider='ollama', model=model, base_url='http://127.0.0.1:11434', temperature=.01,
            max_output_tokens=512, thinking=False, context_window=4096, top_p=.95, top_k=20,
            repeats=3, shuffle_seed=config['seed'], planned_calls=len(rows), task_families=3,
            requests_sha256=pilot.sha(payload), study_config=config, study_config_sha256=pilot.sha(config_bytes),
            source_hashes=old['source_hashes'], dataset_revision=old['dataset_revision'],
            template_sha256=pilot.sha(pilot.TEMPLATE.read_bytes()),
            code_hashes={str(p.relative_to(ROOT)):pilot.sha(p.read_bytes()) for p in
                [Path(__file__), ROOT/'scripts/numeric_checker.py', ROOT/'scripts/judge_pilot.py',
                 ROOT/'scripts/ollama_backend.py']}, human_review_status='pending',
            expected_labels_status='published_intervals_and_source_reproduced_controls_not_expert_gold',
            context='Unchanged public English grading template; only response notation changes.',
            study_status='exploratory_previously_inspected_public_development_tasks')
        directory.mkdir(parents=True)
        (directory/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        (directory/'requests.jsonl').write_bytes(payload)
    print(f'Frozen {len(rows)} calls per model; 64 cells, 32 values, six criteria, three families.')


def analyze(plan, done):
    grouped = defaultdict(list)
    for row in plan:
        grouped[row['pair_id']].append(row)
    cells = []
    for pair_id, rows in sorted(grouped.items()):
        r = rows[0]
        labels = [done[x['request_id']]['result'] for x in rows if x['request_id'] in done]
        complete = len(labels) == len(rows)
        p, n = sum(labels), len(labels)
        check = check_numeric(r['response'], r['bounds'], r['unit'])
        cells.append(dict(pair_id=pair_id, **{k:r[k] for k in
            ['task_id','criterion_id','value','roles','notation','expected_from_design']},
            valid=n, planned=len(rows), passes=p,
            errors=sum(y != r['expected_from_design'] for y in labels),
            majority=int(p>n/2) if complete else None,
            unstable=bool(0<p<n) if complete else None,
            repeat_disagreement=2*p*(n-p)/(n*(n-1)) if complete else None,
            checker=check))
    result = dict(cells=cells, complete=all(c['valid']==c['planned'] for c in cells))
    if not result['complete']:
        return result
    lookup = {(c['task_id'],c['criterion_id'],c['value'],c['notation']):c for c in cells}
    pairs=[]
    for c in cells:
        if c['notation'] != 'decimal': continue
        other=lookup[(c['task_id'],c['criterion_id'],c['value'],'scientific')]
        pairs.append(dict(task_id=c['task_id'],criterion_id=c['criterion_id'],value=c['value'],
            changed=int(c['majority']!=other['majority']),
            decimal_error=int(c['majority']!=c['expected_from_design']),
            scientific_error=int(other['majority']!=other['expected_from_design']),
            repeat_disagreement=(c['repeat_disagreement']+other['repeat_disagreement'])/2))
    rates=[]
    for task in sorted({c['task_id'] for c in cells}):
        for notation in ['decimal','scientific']:
            subset=[c for c in cells if c['task_id']==task and c['notation']==notation]
            pos=[c for c in subset if c['expected_from_design']==1]
            neg=[c for c in subset if c['expected_from_design']==0]
            nominal=[c for c in subset if 'nominal' in c['roles']]
            # Overlapping nominal/inside positions are excluded from this contrast.
            boundary=[c for c in pos if 'nominal' not in c['roles']]
            rates.append(dict(task_id=task,notation=notation,
                errors=sum(c['errors'] for c in subset),valid=sum(c['valid'] for c in subset),
                false_approvals=sum(c['passes'] for c in neg),unmet_calls=sum(c['valid'] for c in neg),
                false_rejections=sum(c['valid']-c['passes'] for c in pos),met_calls=sum(c['valid'] for c in pos),
                nominal_errors=sum(c['errors'] for c in nominal),nominal_calls=sum(c['valid'] for c in nominal),
                boundary_errors=sum(c['errors'] for c in boundary),boundary_calls=sum(c['valid'] for c in boundary)))
    result.update(pairs=pairs,rates=rates,
        errors=sum(c['errors'] for c in cells),valid=sum(c['valid'] for c in cells),
        changed_pairs=sum(p['changed'] for p in pairs),pair_count=len(pairs),
        unstable_cells=sum(c['unstable'] for c in cells),
        equal_family_error=mean(sum(c['errors'] for c in cells if c['task_id']==t)/sum(c['valid'] for c in cells if c['task_id']==t) for t in {c['task_id'] for c in cells}),
        checker_coverage=sum(c['checker']['verdict'] is not None for c in cells)/len(cells),
        checker_errors=sum(c['checker']['verdict']!=c['expected_from_design'] for c in cells if c['checker']['verdict'] is not None))
    return result


def report(root=RUNS):
    models=[]
    for directory in sorted(Path(root).iterdir()):
        if not (directory/'manifest.json').exists(): continue
        manifest,plan=pilot.load_run(directory)
        events=pilot.load_events(directory)
        for event in events:
            if event['plan_sha256']!=manifest['requests_sha256']:
                raise ValueError('Results belong to a different plan')
        done=pilot.successes(events)
        model=dict(model=manifest['model'],planned=len(plan),failed_attempts=sum(e['status']!='ok' for e in events),**analyze(plan,done))
        (directory/'summary.json').write_text(json.dumps(model,indent=2)+'\n')
        models.append(model)
    output=dict(study_id='boundary-format-v1',generated_utc=pilot.now(),models=models,
        limitation='Local constructed controls, three selected families; no expert or Mercor reference labels, no population confidence intervals.')
    (ROOT/'analysis/boundary-format-v1.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps([{k:m.get(k) for k in ['model','complete','valid','errors','changed_pairs','pair_count','unstable_cells','checker_coverage','checker_errors','failed_attempts']} for m in models],indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','report'])
    args=parser.parse_args()
    (prepare if args.command=='prepare' else report)()
