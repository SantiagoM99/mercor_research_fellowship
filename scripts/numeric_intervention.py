#!/usr/bin/env python3
"""Compare frozen grading prompts on new public task probes; local inference only."""
import argparse
import csv
import json
import random
import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import judge_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "experiments/numeric-intervention-v1.json"
RUNS = ROOT / "runs/numeric-intervention-v1"


def bounds(description):
    match = re.search(r"acceptable range is\s+(-?\s*[\d,.]+)%?\s+to\s+(-?\s*[\d,.]+)", description, re.I)
    if not match:
        raise ValueError("Unsupported rubric interval")
    numbers = [Decimal(re.sub(r"[\s,]", "", v)) for v in match.groups()]
    if numbers[0] >= numbers[1]:
        raise ValueError("Invalid interval")
    return numbers


def records(config, tasks, template, amendment):
    result = []
    for probe in config["probes"]:
        task, cid = probe["task_id"], probe["criterion_id"]
        criterion = json.loads(tasks[task]["Rubric JSON"])[f"criterion {cid}"]["description"]
        lo, hi = bounds(criterion)
        nominal, step = Decimal(probe["nominal"]), Decimal(probe["step"])
        if not lo < nominal < hi or step <= 0:
            raise ValueError("Nominal must be interior and perturbation positive")
        variants = [("nominal", nominal), ("lower_edge", lo), ("upper_edge", hi),
                    ("below", lo-step), ("above", hi+step)]
        for variant, value in variants:
            stimulus = f"{task}-c{cid}-{variant}"
            for language in config["languages"]:
                response = probe["responses"][language].format(value=str(value))
                base_prompt = template.format(criterion_description=criterion, solution=response)
                for arm in config["arms"]:
                    prompt = base_prompt if arm == "original" else base_prompt + "\n\n" + amendment
                    for repeat in range(config["repeats"]):
                        result.append(dict(request_id=f"{stimulus}:{arm}:{language}:r{repeat}",
                            stimulus_id=stimulus, pair_id=f"{stimulus}-{arm}", task_id=task,
                            criterion_id=cid, language=language, arm=arm, repeat=repeat, variant=variant,
                            response=response, criterion=criterion, value=str(value), bounds=[str(lo),str(hi)],
                            expected_from_design=int(lo <= value <= hi), prompt=prompt,
                            prompt_sha256=pilot.sha(prompt.encode())))
    random.Random(config["seed"]).shuffle(result)
    return result


def prepare(root=RUNS):
    config_bytes = CONFIG.read_bytes()
    config = json.loads(config_bytes)
    dataset = ROOT / "data/apex-v1-extended"
    source_bytes = (dataset / "train.csv").read_bytes()
    provenance = json.loads((dataset / "manifest.json").read_text())
    if pilot.sha(source_bytes) != provenance["files"]["data/train.csv"]["sha256"]:
        raise ValueError("Pinned dataset changed")
    with (dataset / "train.csv").open(newline="") as stream:
        tasks = {r["Task ID"]:r for r in csv.DictReader(stream)}
    prior = set()
    for directory in (ROOT / "runs/local-comparison-v1").iterdir():
        _, rows = pilot.load_run(directory)
        prior.update(str(r["task_id"]) for r in rows)
    if prior.intersection(p["task_id"] for p in config["probes"]):
        raise ValueError("New-task probes overlap earlier comparison")
    amendment_bytes = (ROOT / config["amendment_file"]).read_bytes()
    template_bytes = pilot.TEMPLATE.read_bytes()
    plan = records(config, tasks, template_bytes.decode(), amendment_bytes.decode())
    payload = "".join(json.dumps(r,ensure_ascii=False)+"\n" for r in plan).encode()
    directories = [Path(root)/m.replace(":","-") for m in config["models"]]
    if any(d.exists() for d in directories):
        raise ValueError("Choose a new run root; existing plans are immutable")
    for model, directory in zip(config["models"], directories):
        manifest = dict(schema_version=3, study_id=config["study_id"], created_utc=pilot.now(),
            provider="ollama", model=model, base_url="http://127.0.0.1:11434",
            temperature=.01, max_output_tokens=512, thinking=False, context_window=4096,
            top_p=.95, top_k=20, repeats=config["repeats"], shuffle_seed=config["seed"],
            planned_calls=len(plan), task_families=3, requests_sha256=pilot.sha(payload),
            study_config=config, study_config_sha256=pilot.sha(config_bytes),
            template_sha256=pilot.sha(template_bytes), amendment_sha256=pilot.sha(amendment_bytes),
            amendment=amendment_bytes.decode(), dataset_sha256=pilot.sha(source_bytes),
            dataset_revision=provenance["revision"], earlier_task_ids=sorted(prior),
            human_review_status="pending", expected_labels_status="published_numeric_predicates_not_expert_gold",
            study_status="exploratory_prompt_intervention_on_new_public_tasks",
            context="Same source rubric and response; clarified arm appends a fixed English numeric-rule instruction.")
        directory.mkdir(parents=True)
        (directory/"requests.jsonl").write_bytes(payload)
        (directory/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        print(f"Frozen {model}: {len(plan)} calls, two interleaved prompt conditions; no calls made.")


def metrics(directory):
    summary = pilot.summarize(directory)
    manifest, plan = pilot.load_run(directory)
    done = pilot.successes(pilot.load_events(directory))
    groups = defaultdict(list)
    for row in plan:
        groups[(row["stimulus_id"],row["language"],row["arm"])].append(row)
    cells=[]
    for (stimulus, language, arm), rows in sorted(groups.items()):
        labels = [done[r["request_id"]]["result"] for r in rows if r["request_id"] in done]
        expected=rows[0]["expected_from_design"]
        cells.append(dict(stimulus_id=stimulus,task_id=rows[0]["task_id"],variant=rows[0]["variant"],
            language=language,arm=arm,expected=expected,planned=len(rows),valid=len(labels),passes=sum(labels),
            errors=sum(v!=expected for v in labels), majority=int(sum(labels)>len(labels)/2) if len(labels)==len(rows) else None))
    rates=[]
    for task in ["all"]+sorted({c["task_id"] for c in cells}):
        for arm in ["original","clarified"]:
            for lang in ["en","es"]:
                selected=[c for c in cells if c["arm"]==arm and c["language"]==lang and (task=="all" or c["task_id"]==task)]
                valid=sum(c["valid"] for c in selected)
                positives=sum(c["valid"] for c in selected if c["expected"]==1)
                negatives=sum(c["valid"] for c in selected if c["expected"]==0)
                errors=sum(c["errors"] for c in selected)
                rates.append(dict(task_id=task,arm=arm,language=lang,valid=valid,
                    planned=sum(c["planned"] for c in selected),errors=errors,error_rate=errors/valid if valid else None,
                    false_accepts=sum(c["passes"] for c in selected if c["expected"]==0),negative_valid=negatives,
                    false_rejects=sum(c["valid"]-c["passes"] for c in selected if c["expected"]==1),positive_valid=positives))
    lookup={(c["stimulus_id"],c["language"],c["arm"]):c for c in cells}
    changes=[]
    for base in [c for c in cells if c["arm"]=="original"]:
        other=lookup[(base["stimulus_id"],base["language"],"clarified")]
        if base["majority"] is None or other["majority"] is None:
            continue
        before,after=base["majority"]!=base["expected"],other["majority"]!=other["expected"]
        changes.append(dict(stimulus_id=base["stimulus_id"],task_id=base["task_id"],language=base["language"],
            repaired=bool(before and not after),regressed=bool(after and not before),
            error_fraction_change=(other["errors"]-base["errors"])/base["planned"]))
    return dict(model=manifest["model"],planned=summary["planned"],valid=summary["valid"],
        failed_attempts=summary["failed_attempts"],cells=cells,rates=rates,paired_changes=changes)


def report(root=RUNS):
    directories=sorted(d for d in Path(root).iterdir() if (d/"manifest.json").exists())
    manifests=[pilot.load_run(d)[0] for d in directories]
    if not manifests or len({m["requests_sha256"] for m in manifests})!=1:
        raise ValueError("Models must have identical requests")
    config=manifests[0]["study_config"]
    if sorted(m["model"] for m in manifests)!=sorted(config["models"]):
        raise ValueError("Missing or duplicate planned models")
    result=dict(study_id=config["study_id"],generated_utc=pilot.now(),config=config,models=[metrics(d) for d in directories])
    result["models"].sort(key=lambda m:config["models"].index(m["model"]))
    result["complete"]=all(m["valid"]==m["planned"] for m in result["models"])
    output=ROOT/"analysis/numeric-intervention-v1.json"
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    for key in ["cells","rates","paired_changes"]:
        rows=[dict(model=m["model"],**r) for m in result["models"] for r in m[key]]
        if rows:
            with (ROOT/f"analysis/numeric-intervention-v1-{key}.csv").open("w",newline="") as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(f"Wrote {output}; complete={result['complete']}")
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["prepare","run","report"])
    parser.add_argument("--root",type=Path,default=RUNS)
    parser.add_argument("--model",choices=["qwen3:4b","gemma3:4b"])
    parser.add_argument("--max-calls",type=int,default=180)
    args=parser.parse_args()
    if args.command=="prepare": prepare(args.root)
    elif args.command=="report": report(args.root)
    else:
        if not args.model: parser.error("run requires --model")
        directory=args.root/args.model.replace(":","-")
        pilot.run(argparse.Namespace(output=directory,max_calls=args.max_calls,delay=0,timeout=180))
        summary=pilot.summarize(directory)
        if summary["valid"]!=summary["planned"]: raise SystemExit(2)


if __name__=="__main__": main()
