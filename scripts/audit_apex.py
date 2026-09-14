#!/usr/bin/env python3
"""Audit the pinned public APEX CSV, offline, without model calls.

Dependency edges are author-declared structure, not empirical causal effects.
Run from any directory. Only Python's standard library is required.
"""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/apex-v1-extended"
OUT = ROOT / "analysis"


def descendants(node, children):
    found, pending = set(), list(children[node])
    while pending:
        child = pending.pop()
        if child not in found:
            found.add(child)
            pending.extend(children[child])
    return found


def audit(rows):
    domains = defaultdict(lambda: {
        "tasks": 0, "criteria": 0, "dependent_criteria": 0,
        "primary_criteria": 0, "type_combinations": Counter(),
    })
    flat, tasks, errors, cycles = [], [], [], []
    raw_types, ratings, weights = Counter(), Counter(), Counter()
    for row in rows:
        task_id = str(row["Task ID"])
        rubric = json.loads(row["Rubric JSON"])
        criteria = {int(k.split()[-1]): v for k, v in rubric.items()}
        if len(criteria) != len(rubric):
            raise ValueError(f"Duplicate parsed criterion ID in task {task_id}")
        children = defaultdict(set)
        edges = []
        for cid, criterion in criteria.items():
            for parent in criterion.get("dependent_criteria", []):
                if parent not in criteria or parent == cid:
                    errors.append({"task_id": task_id, "criterion_id": cid, "reference": parent})
                else:
                    children[parent].add(cid)
                    edges.append((parent, cid))
        reach = {cid: descendants(cid, children) for cid in criteria}
        cyclic = [cid for cid in criteria if cid in reach[cid]]
        if cyclic:
            cycles.append({"task_id": task_id, "criteria": cyclic})
        domain = domains[row["Domain"]]
        domain["tasks"] += 1
        domain["criteria"] += len(criteria)
        for cid, criterion in criteria.items():
            types = criterion.get("criterion_type", [])
            normalized = " + ".join(sorted(set(types)))
            domain["type_combinations"][normalized] += 1
            raw_types[json.dumps(types)] += 1
            ratings[json.dumps(criterion.get("human_rating"))] += 1
            weights[str(criterion.get("weight"))] += 1
            dependent = bool(criterion.get("dependent_criteria", []))
            primary = criterion.get("weight") == "Primary objective(s)"
            domain["dependent_criteria"] += dependent
            domain["primary_criteria"] += primary
            flat.append({
                "task_id": task_id, "domain": row["Domain"], "criterion_id": cid,
                "criterion_type_normalized": normalized,
                "weight": criterion.get("weight"),
                "dependent_criteria": json.dumps(criterion.get("dependent_criteria", [])),
                "descendant_count": len(reach[cid] - {cid}),
                "direct_score_pp": 100 / len(criteria),
                "structural_exposure_pp": 100 * len(reach[cid] | {cid}) / len(criteria),
                "description": criterion.get("description", ""),
            })
        root = max(criteria, key=lambda cid: len(reach[cid]))
        tasks.append({
            "task_id": task_id, "domain": row["Domain"], "criteria": len(criteria),
            "dependent_criteria": sum(bool(c.get("dependent_criteria", [])) for c in criteria.values()),
            "dependency_edges": len(edges),
            "primary_criteria": sum(c.get("weight") == "Primary objective(s)" for c in criteria.values()),
            "max_descendants": len(reach[root] - {root}), "max_reach_criterion": root,
            "max_structural_exposure_pp": 100 * len(reach[root] | {root}) / len(criteria),
            "attachment_count": len(row["File Attachments"].splitlines()),
        })
    for domain in domains.values():
        domain["mean_criteria"] = domain["criteria"] / domain["tasks"]
        domain["primary_share_pct"] = 100 * domain["primary_criteria"] / domain["criteria"]
        domain["type_combinations"] = dict(domain["type_combinations"])
    return {
        "tasks": len(rows), "criteria": len(flat), "domains": dict(domains),
        "dependent_criteria": sum(d["dependent_criteria"] for d in domains.values()),
        "tasks_with_dependencies": sum(t["dependency_edges"] > 0 for t in tasks),
        "raw_type_combinations": dict(raw_types), "human_rating_values": dict(ratings),
        "weight_values": dict(weights), "invalid_dependency_references": errors,
        "dependency_cycles": cycles,
    }, tasks, flat


def write_csv(path, records):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main():
    manifest = json.loads((DATA / "manifest.json").read_text())
    raw = (DATA / "train.csv").read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    expected = manifest["files"]["data/train.csv"]["sha256"]
    if actual != expected:
        raise ValueError("CSV checksum differs from downloaded manifest")
    with (DATA / "train.csv").open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    if len({row["Task ID"] for row in rows}) != len(rows):
        raise ValueError("Duplicate task IDs")
    summary, tasks, flat = audit(rows)
    summary["provenance"] = {"dataset_revision": manifest["revision"], "csv_sha256": actual}
    OUT.mkdir(exist_ok=True)
    (OUT / "apex_audit.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_csv(OUT / "apex_tasks.csv", tasks)
    write_csv(OUT / "apex_criteria.csv", flat)
    lines = [
        "# Public APEX development-set audit", "",
        "Generated by `python3 scripts/audit_apex.py`. No LLM runs or human judgments are included.", "",
        f"Source: [mercor/APEX-v1-extended](https://huggingface.co/datasets/mercor/APEX-v1-extended/tree/{manifest['revision']}).",
        f"Revision: `{manifest['revision']}`; CSV SHA-256: `{actual}`.", "",
        f"**{summary['tasks']} tasks; {summary['criteria']:,} criteria; {summary['dependent_criteria']} criteria with declared dependencies across {summary['tasks_with_dependencies']} tasks.**", "",
        "| Domain | Tasks | Criteria | With dependencies | Primary objectives | Primary share |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, d in sorted(summary["domains"].items()):
        lines.append(f"| {name} | {d['tasks']} | {d['criteria']} | {d['dependent_criteria']} | {d['primary_criteria']} | {d['primary_share_pct']:.1f}% |")
    lines += ["", "## What deserves follow-up", "",
        "1. **A concrete propagation example.** Task 2108 criterion 1 has five downstream criteria in the declared graph. Under equal criterion scoring, its own label is 16.7 points; the criterion plus all reachable descendants cover 100 points. This is structural exposure, not evidence that one error actually causes all six failures. Compare matched responses with a seeded upstream error and inspect which labels change.",
        "2. **Priority and scoring are different metadata.** Finance marks 80/232 criteria as primary objectives; Medicine marks 349/419. This is an item-pooled descriptive contrast, not the average task score. Compare the canonical score with a separately labeled primary-objective diagnostic on the same responses; neither is automatically the better measure.",
        "3. **Reasoning is not the opposite of numeric.** All 11 criteria in task 2287 are tagged only Reasoning, including its numerical IRR, MOIC and NPV requirements. Keep criterion_type and add an independently reviewed numerical-versus-semantic scoring-mode annotation. Do not infer that distinction from the original tags.",
        "4. **Metadata is not human evaluation coverage.** The human_rating field contains 1,136 false and four true values. Without a schema definition and linked responses/raters, these values do not establish how many items were human graded.",
        "5. **Representation is not organizational evidence.** The two orderings of the Extraction/Reasoning pair occur 423 and 138 times. Normalize as sets for analysis; this does not establish whether Mercor has previously analyzed them.", "",
        "## Five candidate pilot families", "",
        "| Task | Domain | Criteria | Declared edges | Largest downstream set | Starting criterion |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for t in tasks:
        if t["task_id"] in {"2287", "2108", "2145", "1172", "1242"}:
            lines.append(f"| {t['task_id']} | {t['domain']} | {t['criteria']} | {t['dependency_edges']} | {t['max_descendants']} | {t['max_reach_criterion']} |")
    lines += ["", "## A traceable dependency example: task 2108", "",
        "Arrows show the rubric's declared prerequisite relationships. All five other criteria are reachable from enterprise value; this graph does not show observed model failures.", "",
        "```mermaid", "flowchart LR",
        '    C1["1. Enterprise value"] --> C2["2. EV / revenue"]',
        '    C1 --> C3["3. EV / EBITDA"]',
        '    C1 --> C4["4. Equity value"]',
        '    C4 --> C5["5. Equity per share"]',
        '    C2 --> C6["6. Valuation conclusion"]',
        '    C3 --> C6', '    C5 --> C6', "```", "",
        "## Graph integrity", "",
        f"Invalid/self references: {len(summary['invalid_dependency_references'])}; tasks with cycles: {len(summary['dependency_cycles'])}.", "",
        "Declared dependency edges motivate clustered analysis. They do not demonstrate a violation of conditional independence, prove double counting, or quantify error propagation without response-level data.", "",
        "## Scope", "",
        "This is the 100-case public development set. It provides no access to the 400 hidden evaluation cases, historical trajectories, or internal human labels. Raw descriptions and fields are retained in apex_criteria.csv for traceability. The downloaded dataset card contains attribution and intended-use terms. No dataset content was used to train or tune a model.", "",
    ]
    (OUT / "APEX data audit.md").write_text("\n".join(lines))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
