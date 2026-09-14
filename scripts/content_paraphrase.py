#!/usr/bin/env python3
"""Frozen local factorial diagnostic: content, wording and grading language."""
import argparse
import csv
import json
import random
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import mean

import judge_pilot as pilot
from measure_sensitivity import finance_values, round_half_up
from verify_followup_sources import advertising, nps

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'experiments/content-paraphrase-v1.json'
RUNS = ROOT / 'runs/content-paraphrase-v1'
OUTPUT = ROOT / 'analysis/content-paraphrase-v1.json'


def numbers(text):
    return [Decimal(re.sub(r'[\s$]', '', n))
            for n in re.findall(r'-?\s*\$?\d+(?:\.\d+)?', text)]


def records(config, tasks, templates):
    rows = []
    for p in config['probes']:
        task, cid = p['task_id'], p['criterion_id']
        original = json.loads(tasks[task]['Rubric JSON'])[f'criterion {cid}']['description']
        if p['rubrics']['en']['original'] != original:
            raise ValueError('Original criterion must match the pinned dataset exactly')
        lo, hi = map(Decimal, p['bounds'])
        if numbers(original)[-2:] != [lo, hi] or lo >= hi:
            raise ValueError('Bounds do not match the published rubric')
        for lang in config['languages']:
            for wording in config['wordings']:
                if numbers(p['rubrics'][lang][wording]) != numbers(original):
                    raise ValueError('Translation/paraphrase changed numbers or their order')
            if p['rubrics'][lang]['original'] == p['rubrics'][lang]['paraphrase']:
                raise ValueError('Paraphrase must differ')
        for state, value in p['values'].items():
            expected = int(lo <= Decimal(value) <= hi)
            if expected != int(state == 'correct'):
                raise ValueError('Content control is mislabeled')
            for language in config['languages']:
                response = p['responses'][language].format(value=value)
                for grading_language in config['languages']:
                    for wording in config['wordings']:
                        criterion = p['rubrics'][grading_language][wording]
                        prompt = templates[grading_language].format(criterion_description=criterion, solution=response)
                        pair = f'{task}-c{cid}-{state}-{grading_language}-{wording}'
                        for repeat in range(config['repeats']):
                            rows.append(dict(request_id=f'{pair}:{language}:r{repeat}', pair_id=pair,
                                task_id=task, criterion_id=cid, state=state, language=language,
                                grading_language=grading_language, wording=wording, repeat=repeat,
                                expected_from_design=expected, value=value, bounds=p['bounds'],
                                criterion=criterion, response=response, prompt=prompt,
                                prompt_sha256=pilot.sha(prompt.encode())))
    random.Random(config['seed']).shuffle(rows)
    return rows


def prepare(root=RUNS):
    config_bytes = CONFIG.read_bytes()
    config = json.loads(config_bytes)
    data = ROOT / 'data/apex-v1-extended'
    provenance = json.loads((data / 'manifest.json').read_text())
    source_paths = ['data/train.csv', 'documents/145/Campaign_Portfolio.csv',
                    'documents/1122/Survey.csv', 'documents/2287/KatNip.pdf']
    hashes = {}
    for source in source_paths:
        path = data / ('train.csv' if source == 'data/train.csv' else source)
        digest = pilot.sha(path.read_bytes())
        if digest != provenance['files'][source]['sha256']:
            raise ValueError(f'Pinned source changed: {source}')
        hashes[source] = digest
    with (data / 'train.csv').open(newline='') as stream:
        tasks = {r['Task ID']: r for r in csv.DictReader(stream)}
    values = {}
    for task, cid, name, calculate, places in [
        ('145', 2, 'Campaign_Portfolio.csv', advertising, '0.01'),
        ('1122', 1, 'Survey.csv', nps, '1')]:
        with (data/'documents'/task/name).open(newline='', encoding='utf-8-sig') as stream:
            values[(task, cid)] = calculate(list(csv.DictReader(stream)))['value'].quantize(Decimal(places))
    values.update({('2287', cid): Decimal(str(round_half_up(v, 1))) for cid, v in finance_values().items()})
    for p in config['probes']:
        if values[(p['task_id'], p['criterion_id'])] != Decimal(p['values']['correct']):
            raise ValueError('Correct control differs from source reproduction')
    template_bytes = {'en': pilot.TEMPLATE.read_bytes(), 'es': (ROOT / config['spanish_template']).read_bytes()}
    plan = records(config, tasks, {k: v.decode() for k, v in template_bytes.items()})
    payload = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in plan).encode()
    directories = [Path(root) / m.replace(':', '-') for m in config['models']]
    if any(d.exists() for d in directories):
        raise ValueError('Existing runs are immutable; choose a new root')
    if len(plan) != 288 or len({r['request_id'] for r in plan}) != 288:
        raise ValueError('Expected 288 unique calls per model')
    code_hashes = {str(p.relative_to(ROOT)): pilot.sha(p.read_bytes()) for p in
                   [Path(__file__), ROOT/'scripts/judge_pilot.py', ROOT/'scripts/ollama_backend.py',
                    ROOT/'scripts/measure_sensitivity.py', ROOT/'scripts/verify_followup_sources.py']}
    for model, directory in zip(config['models'], directories):
        manifest = dict(schema_version=3, study_id=config['study_id'], created_utc=pilot.now(),
            provider='ollama', model=model, base_url='http://127.0.0.1:11434',
            temperature=.01, max_output_tokens=512, thinking=False, context_window=4096,
            top_p=.95, top_k=20, repeats=config['repeats'], shuffle_seed=config['seed'],
            planned_calls=len(plan), task_families=3, requests_sha256=pilot.sha(payload),
            study_config=config, study_config_sha256=pilot.sha(config_bytes),
            template_hashes={k: pilot.sha(v) for k, v in template_bytes.items()},
            source_hashes=hashes, dataset_revision=provenance['revision'], code_hashes=code_hashes,
            human_review_status='pending', expected_labels_status='source_reproduced_numeric_controls_not_expert_gold',
            context='Response language x grading language (instructions and criterion together) x rubric wording x content. No numeric clarification appended.',
            study_status='exploratory_previously_inspected_public_development_tasks')
        directory.mkdir(parents=True)
        (directory / 'requests.jsonl').write_bytes(payload)
        (directory / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        print(f'Frozen {model}: {len(plan)} calls; independent human review pending.')


def analyze(plan, done):
    groups = defaultdict(list)
    fields = ['task_id', 'criterion_id', 'state', 'language', 'grading_language', 'wording']
    for row in plan:
        groups[tuple(row[f] for f in fields)].append(row)
    cells = []
    for key, rows in sorted(groups.items()):
        labels = [done[r['request_id']]['result'] for r in rows if r['request_id'] in done]
        n, p = len(labels), sum(labels)
        complete = n == len(rows)
        cells.append(dict(zip(fields, key), expected=rows[0]['expected_from_design'],
            valid=n, planned=len(rows), passes=p, pass_fraction=p/n if n else None,
            majority=int(p > n/2) if complete else None,
            errors=sum(x != rows[0]['expected_from_design'] for x in labels),
            unstable=bool(0 < p < n) if complete else None,
            within_disagreement=2*p*(n-p)/(n*(n-1)) if complete and n > 1 else None))
    lookup = {tuple(c[f] for f in fields): c for c in cells}
    paired = []
    for dimension, base_value, target_value, kind in [
        ('state', 'incorrect', 'correct', 'content'),
        ('wording', 'original', 'paraphrase', 'paraphrase'),
        ('grading_language', 'en', 'es', 'grading_language'),
        ('language', 'en', 'es', 'response_language')]:
        for c in cells:
            if c[dimension] != base_value:
                continue
            target = dict(c, **{dimension: target_value})
            other = lookup[tuple(target[f] for f in fields)]
            if c['majority'] is None or other['majority'] is None:
                continue
            before_error = c['majority'] != c['expected']
            after_error = other['majority'] != other['expected']
            paired.append(dict(kind=kind, **{f: c[f] for f in fields if f != dimension},
                before=c['majority'], after=other['majority'],
                changed=int(c['majority'] != other['majority']),
                detected=int(c['majority'] == 0 and other['majority'] == 1) if kind == 'content' else None,
                reversed=int(c['majority'] == 1 and other['majority'] == 0) if kind == 'content' else None,
                repaired=int(before_error and not after_error) if kind != 'content' else None,
                regressed=int(not before_error and after_error) if kind != 'content' else None,
                pass_fraction_change=other['pass_fraction']-c['pass_fraction'],
                fraction_changed=int(other['passes'] != c['passes']),
                absolute_error_change=other['errors']/other['valid']-c['errors']/c['valid']))
    rates = []
    if len(done) == len(plan):
        for language in ['en', 'es']:
            task_rates = []
            for task in sorted({c['task_id'] for c in cells}):
                selected = [c for c in cells if c['language'] == language and c['task_id'] == task]
                pos = [c for c in selected if c['expected'] == 1]
                neg = [c for c in selected if c['expected'] == 0]
                row = dict(task_id=task, language=language,
                    valid=sum(c['valid'] for c in selected), errors=sum(c['errors'] for c in selected),
                    false_accepts=sum(c['passes'] for c in neg), negative_valid=sum(c['valid'] for c in neg),
                    false_rejects=sum(c['valid']-c['passes'] for c in pos), positive_valid=sum(c['valid'] for c in pos),
                    unstable_cells=sum(c['unstable'] for c in selected), cells=len(selected),
                    repeat_disagreement=mean(c['within_disagreement'] for c in selected))
                row['error_rate'] = row['errors']/row['valid']
                for kind in ['content', 'paraphrase', 'grading_language']:
                    pairs = [p for p in paired if p['kind'] == kind and p['task_id'] == task and p['language'] == language]
                    key = 'detected' if kind == 'content' else 'changed'
                    row[kind+'_count'] = sum(p[key] for p in pairs)
                    row[kind+'_pairs'] = len(pairs)
                    row[kind+'_rate'] = row[kind+'_count']/len(pairs)
                task_rates.append(row)
            rates.extend(task_rates)
            macro = dict(task_id='equal_task_macro', language=language)
            for key in task_rates[0]:
                if key in ['task_id', 'language']:
                    continue
                macro[key] = mean(t[key] for t in task_rates) if key.endswith('_rate') or key == 'repeat_disagreement' else sum(t[key] for t in task_rates)
            rates.append(macro)
    return dict(cells=cells, pairs=paired, rates=rates)


def report(root=RUNS):
    directories = sorted(d for d in Path(root).iterdir() if (d/'manifest.json').exists())
    loaded = [pilot.load_run(d) for d in directories]
    if not loaded or len({m['requests_sha256'] for m, _ in loaded}) != 1:
        raise ValueError('Models must have identical plans')
    config = loaded[0][0]['study_config']
    if sorted(m['model'] for m, _ in loaded) != sorted(config['models']):
        raise ValueError('Missing or duplicate models')
    models = []
    for directory, (manifest, plan) in zip(directories, loaded):
        summary = pilot.summarize(directory)
        done = pilot.successes(pilot.load_events(directory))
        models.append(dict(model=manifest['model'], planned=len(plan), valid=len(done),
            failed_attempts=summary['failed_attempts'], **analyze(plan, done)))
    models.sort(key=lambda m: config['models'].index(m['model']))
    result = dict(study_id=config['study_id'], generated_utc=pilot.now(), config=config,
        complete=all(m['valid'] == m['planned'] for m in models), models=models,
        limitation='Three selected development tasks, six criteria; design labels and unreviewed translations. Rates use majority over three repeats; macro rates weight tasks equally. Pooled counts are descriptive and do not define macro rates.')
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    for key in ['cells', 'pairs', 'rates']:
        rows = [dict(model=m['model'], **r) for m in models for r in m[key]]
        if rows:
            with OUTPUT.with_name(OUTPUT.stem+'-'+key+'.csv').open('w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for row in rows for k in row)))
                writer.writeheader(); writer.writerows(rows)
    print(f'Wrote {OUTPUT}; complete={result["complete"]}')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'report'])
    parser.add_argument('--root', type=Path, default=RUNS)
    parser.add_argument('--model', choices=['qwen3:4b', 'gemma3:4b'])
    parser.add_argument('--max-calls', type=int, default=288)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.root)
    elif args.command == 'report':
        report(args.root)
    else:
        if not args.model:
            parser.error('run requires --model')
        directory = args.root / args.model.replace(':', '-')
        pilot.run(argparse.Namespace(output=directory, max_calls=args.max_calls, delay=0, timeout=180))
        summary = pilot.summarize(directory)
        if summary['valid'] != summary['planned']:
            raise SystemExit(2)


if __name__ == '__main__':
    main()
