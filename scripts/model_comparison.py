#!/usr/bin/env python3
"""Freeze and execute a local multi-model study with a fixed descriptive analysis."""
import argparse
import csv
import json
import random
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import judge_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments/local-comparison-v1.json"
RUNS = ROOT / "runs/local-comparison-v1"


def model_slug(model):
    return model.replace(":", "-")


def numeric_records(config, tasks, template):
    records = []
    for probe in config["probes"]:
        task, cid = probe["task_id"], probe["criterion_id"]
        criterion = json.loads(tasks[task]["Rubric JSON"])[f"criterion {cid}"]["description"]
        lower, upper = Decimal(probe["lower"]), Decimal(probe["upper"])
        # Ensure hand-transcribed thresholds are visibly present in the source.
        normalized = criterion.replace(",", "").replace("$", "")
        if probe["lower"] not in normalized or probe["upper"] not in normalized:
            raise ValueError(f"Bounds absent from original rubric: {task}/{cid}")
        for variant in probe["variants"]:
            value = variant["value"]
            expected = int(lower <= Decimal(value) <= upper)
            for lang, response_template in probe["responses"].items():
                response = response_template.format(value=value)
                prompt = template.format(criterion_description=criterion, solution=response)
                pair = f"{task}-numeric-c{cid}-{variant['name']}"
                for repeat in range(config["repeats"]):
                    records.append({"request_id": f"{pair}:{lang}:c{cid}:r{repeat}",
                        "task_id": task, "pair_id": pair, "criterion_id": cid,
                        "language": lang, "repeat": repeat, "experiment": "numeric_probe",
                        "variant": variant["name"], "value": value,
                        "accepted_bounds": [probe["lower"], probe["upper"]],
                        "expected_from_design": expected, "response": response,
                        "prompt": prompt, "prompt_sha256": pilot.sha(prompt.encode())})
    return records


def prepare(config_path=CONFIG, root=RUNS):
    config_bytes = Path(config_path).read_bytes()
    config = json.loads(config_bytes)
    dataset = ROOT / "data/apex-v1-extended"
    provenance = json.loads((dataset / "manifest.json").read_text())
    data_bytes = (dataset / "train.csv").read_bytes()
    if pilot.sha(data_bytes) != provenance["files"]["data/train.csv"]["sha256"]:
        raise ValueError("Dataset checksum changed")
    with (dataset / "train.csv").open(newline="") as stream:
        tasks = {r["Task ID"]: r for r in csv.DictReader(stream)}
    template = pilot.TEMPLATE.read_text()
    extra = numeric_records(config, tasks, template)
    directories = [Path(root) / model_slug(m) for m in config["models"]]
    if any(d.exists() for d in directories):
        raise ValueError("Study directories already exist; use a new study root")
    for model, directory in zip(config["models"], directories):
        pilot.prepare(argparse.Namespace(output=directory, provider="ollama", model=model,
            repeats=config["repeats"], seed=config["seed"], max_output_tokens=512,
            thinking_budget=0, thinking=False, context_window=4096))
        manifest, original = pilot.load_run(directory)
        for row in original:
            row.update(experiment="matched_response", variant=row["pair_id"].split("-", 1)[1])
        records = original + extra
        random.Random(config["seed"]).shuffle(records)
        payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records).encode()
        manifest.update(study_id=config["study_id"], study_config_sha256=pilot.sha(config_bytes),
            study_config=config, task_families=3, planned_calls=len(records),
            dataset_revision=provenance["revision"], dataset_sha256=pilot.sha(data_bytes),
            requests_sha256=pilot.sha(payload),
            selection=config["selection"],
            limitation="Selected criterion probes, not full task solutions or a population benchmark. Portuguese is secondary.")
        (directory / "requests.jsonl").write_bytes(payload)
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Frozen {model}: {len(records)} calls, identical requests across judges.")


def metrics(directory):
    summary = pilot.summarize(directory)  # Validates plan/event/configuration linkage.
    manifest, plan = pilot.load_run(directory)
    completed = pilot.successes(pilot.load_events(directory))
    groups = defaultdict(list)
    for row in plan:
        groups[(row["experiment"], row["task_id"], row["pair_id"], row["criterion_id"], row["language"])].append(row)
    cells = []
    for (experiment, task, pair, cid, language), rows in sorted(groups.items()):
        labels = [completed[r["request_id"]]["result"] for r in rows if r["request_id"] in completed]
        cells.append(dict(experiment=experiment, task_id=task, pair_id=pair, criterion_id=cid,
            language=language, variant=rows[0]["variant"], expected=rows[0]["expected_from_design"],
            planned=len(rows), valid=len(labels), passes=sum(labels),
            pass_fraction=sum(labels)/len(labels) if labels else None))
    rates = []
    for experiment in ["matched_response", "numeric_probe"]:
        for language in sorted({c["language"] for c in cells if c["experiment"] == experiment}):
            subset = [c for c in cells if c["experiment"] == experiment and c["language"] == language]
            positives, negatives = [c for c in subset if c["expected"] == 1], [c for c in subset if c["expected"] == 0]
            rejected = sum(c["valid"] - c["passes"] for c in positives)
            accepted = sum(c["passes"] for c in negatives)
            np, nn = sum(c["valid"] for c in positives), sum(c["valid"] for c in negatives)
            rates.append(dict(experiment=experiment, language=language,
                false_accepts=accepted, negative_valid=nn,
                false_rejects=rejected, positive_valid=np,
                false_accept_rate=accepted/nn if nn else None,
                false_reject_rate=rejected/np if np else None,
                valid=np+nn, planned=sum(c["planned"] for c in subset)))
    contrasts = []
    lookup = {(c["pair_id"], c["criterion_id"], c["language"]): c for c in cells}
    for en in [c for c in cells if c["language"] == "en"]:
        for language in ["es", "pt"]:
            other = lookup.get((en["pair_id"], en["criterion_id"], language))
            if not other or en["valid"] != en["planned"] or other["valid"] != other["planned"]:
                continue
            n, m, p, q = en["valid"], other["valid"], en["passes"], other["passes"]
            contrasts.append(dict(experiment=en["experiment"], task_id=en["task_id"],
                pair_id=en["pair_id"], criterion_id=en["criterion_id"], language=language,
                other_minus_en=q/m-p/n,
                cross_language_disagreement=(p*(m-q)+(n-p)*q)/(n*m),
                within_en_disagreement=2*p*(n-p)/(n*(n-1)),
                within_other_disagreement=2*q*(m-q)/(m*(m-1))))
    return dict(model=manifest["model"], run=str(Path(directory).relative_to(ROOT)) if Path(directory).is_relative_to(ROOT) else str(directory),
        planned=summary["planned"], valid=summary["valid"], failed_attempts=summary["failed_attempts"],
        cells=cells, rates=rates, contrasts=contrasts,
        model_versions=summary["model_versions_observed"])


def report(root=RUNS, output=None):
    output = Path(output or ROOT / "analysis/local-comparison-v1.json")
    directories = sorted(d for d in Path(root).iterdir() if (d / "manifest.json").exists())
    manifests = [pilot.load_run(d)[0] for d in directories]
    if not manifests or len({m["requests_sha256"] for m in manifests}) != 1:
        raise ValueError("Models must use an identical frozen request plan")
    configs = {m["study_config_sha256"] for m in manifests}
    if len(configs) != 1:
        raise ValueError("Study configurations differ")
    expected_models = manifests[0]["study_config"]["models"]
    if sorted(m["model"] for m in manifests) != sorted(expected_models):
        raise ValueError("Missing or duplicate planned models")
    results = [metrics(d) for d in directories]
    results.sort(key=lambda r: expected_models.index(r["model"]))
    data = dict(study_id=manifests[0]["study_id"], generated_utc=pilot.now(),
        complete=all(r["planned"] == r["valid"] for r in results), models=results,
        study_config=manifests[0]["study_config"], requests_sha256=manifests[0]["requests_sha256"],
        interpretation="Descriptive only. Three selected source tasks, no independent expert review. Repeats/criteria are not independent tasks; agreement can coexist with incorrect judgments.")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {output}; complete={data['complete']}")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "run", "report"])
    parser.add_argument("--root", type=Path, default=RUNS)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-calls", type=int, default=270)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.config, args.root)
    elif args.command == "report":
        report(args.root)
    else:
        if not args.model:
            parser.error("run requires --model; execute one model at a time")
        directory = args.root / model_slug(args.model)
        pilot.run(argparse.Namespace(output=directory, max_calls=args.max_calls, delay=0, timeout=180))
        summary = pilot.summarize(directory)
        if summary["valid"] < summary["planned"]:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
