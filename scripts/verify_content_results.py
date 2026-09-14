#!/usr/bin/env python3
"""Audit raw response/plan identity and regenerated metrics; record artifact hashes."""
import json
from pathlib import Path

import content_paraphrase as study
import judge_pilot as pilot
import ollama_backend

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    report = json.loads(study.OUTPUT.read_text())
    require(report['complete'], 'Analysis must be complete')
    artifacts = []
    archived_code = {}
    models = []
    plan_hashes = set()
    for model in report['models']:
        directory = study.RUNS/model['model'].replace(':', '-')
        manifest, plan = pilot.load_run(directory)
        events = pilot.load_events(directory)
        done = pilot.successes(events)
        runtime = json.loads((directory/'runtime_identity.json').read_text())
        require(len(done) == len(plan) == 288, 'Expected 288 valid calls per model')
        require(manifest['model'] == model['model'], 'Wrong model in report')
        require(manifest['study_config'] == report['config'], 'Report configuration differs from plan')
        require(manifest['study_config_sha256'] == pilot.sha(study.CONFIG.read_bytes()), 'Study config changed')
        config_hash = pilot.sha(json.dumps(manifest, sort_keys=True).encode())
        require(runtime['configuration_sha256'] == config_hash, 'Runtime differs from frozen config')
        for filename, digest in manifest['code_hashes'].items():
            active = ROOT/filename
            if pilot.sha(active.read_bytes()) != digest:
                snapshot = ROOT/'experiments/frozen-code'/report['study_id']/filename
                require(snapshot.is_file() and pilot.sha(snapshot.read_bytes()) == digest,
                        f'No matching execution-time source: {filename}')
                archived_code[filename] = str(snapshot.relative_to(ROOT))
        for filename, digest in manifest['source_hashes'].items():
            path = ROOT/'data/apex-v1-extended'/('train.csv' if filename == 'data/train.csv' else filename)
            require(pilot.sha(path.read_bytes()) == digest, f'Source changed: {filename}')
        for lang, path in [('en', pilot.TEMPLATE), ('es', ROOT/manifest['study_config']['spanish_template'])]:
            require(pilot.sha(path.read_bytes()) == manifest['template_hashes'][lang], 'Grading template changed')
        by_id = {r['request_id']: r for r in plan}
        for row in plan:
            require(pilot.sha(row['prompt'].encode()) == row['prompt_sha256'], 'Prompt hash differs')
        for event in events:
            require(event['request_id'] in by_id, 'Unknown result ID')
            require(event['plan_sha256'] == manifest['requests_sha256'], 'Result belongs to another plan')
            require(event['configuration_sha256'] == config_hash, 'Result belongs to another config')
            require(event['model_requested'] == manifest['model'], 'Wrong requested model')
            require(manifest['created_utc'] <= event['started_utc'], 'Plan was frozen after inference started')
            if event['status'] == 'ok':
                require(event['response']['model'] == manifest['model'], 'Provider returned a different model')
                require(event['runtime_identity'] == runtime, 'Runtime identity drift')
                parsed = ollama_backend.parse(event['response'], pilot.validate_result)
                require(parsed['result'] == event['result'] and parsed['reason'] == event['reason'], 'Raw and parsed judgments differ')
                require(event['usage']['prompt_eval_count'] + manifest['max_output_tokens'] < manifest['context_window'], 'Potential context truncation')
        recalculated = study.analyze(plan, done)
        for field in ['cells', 'pairs', 'rates']:
            require(recalculated[field] == model[field], f'Analysis does not reproduce: {field}')
        require(len(recalculated['cells']) == 96, 'Unexpected factorial cell count')
        require(all(c['valid'] == c['planned'] == 3 for c in recalculated['cells']), 'Incomplete repeat cells')
        plan_hashes.add(manifest['requests_sha256'])
        models.append(dict(model=model['model'], valid=len(done), failed_attempts=sum(e['status']!='ok' for e in events),
                           cells=len(recalculated['cells']), max_prompt_tokens=max(e['usage']['prompt_eval_count'] for e in done.values())))
        artifacts.extend(directory/p for p in ['manifest.json', 'requests.jsonl', 'runtime_identity.json', 'results.jsonl', 'summary.json'])
    require(len(plan_hashes) == 1, 'Model stimulus plans differ')
    require({m['model'] for m in models} == set(report['config']['models']) and len(models) == 2, 'Missing/duplicate model')
    artifacts.extend([study.CONFIG, ROOT/'proposal/protocols/Contenido y paráfrasis — protocolo.md',
        ROOT/'analysis/Contenido y paráfrasis — resultados.md', study.OUTPUT])
    artifacts.extend(ROOT/f'analysis/content-paraphrase-v1-{name}.csv' for name in ['cells', 'pairs', 'rates'])
    artifacts.extend(ROOT/f'figures/content_paraphrase.{ext}' for ext in ['png', 'pdf', 'svg', 'md'])
    artifacts.extend(ROOT/f'figures/content_paraphrase_detail.{ext}' for ext in ['png', 'pdf', 'svg', 'md'])
    artifacts.extend(ROOT/f'scripts/{name}.py' for name in ['content_paraphrase', 'report_content_paraphrase', 'plot_content_paraphrase', 'verify_content_results'])
    artifacts.extend(ROOT/path for path in archived_code.values())
    record = dict(verified_utc=pilot.now(), study_id=report['study_id'], models=models,
        execution_time_source_snapshots=archived_code,
        checks='Frozen inputs; identical plans; 576 valid raw responses; model identity; context budget; independent metric regeneration.',
        artifacts={str(p.relative_to(ROOT)): pilot.sha(p.read_bytes()) for p in artifacts})
    output = ROOT/'analysis/content-paraphrase-v1-artifacts.json'
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(models=models, artifact_count=len(artifacts), execution_time_source_snapshots=archived_code), indent=2))
    print(output)


if __name__ == '__main__':
    main()
