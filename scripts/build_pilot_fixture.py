#!/usr/bin/env python3
"""Recompute task 1172 from its attached data; construct unreviewed EN/ES stimuli.

This is an arithmetic reproduction and stimulus preparation, not an LLM experiment.
"""
import csv
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/apex-v1-extended"


def calculate(rows):
    with localcontext() as context:
        context.prec = 50
        values = [(Decimal(r["2020"].replace(",", "")), Decimal(r["2024"].replace(",", ""))) for r in rows]
        # Eight forecast years / four historical years = 2; no intermediate rounding.
        population = sum(end ** 3 / start ** 2 for start, end in values)
        unrounded = {
            "population_2024": sum(end for _, end in values),
            "population_2032": population,
            "interested_people": population * Decimal("0.15"),
            "tam_usd": population * Decimal("0.15") * 50,
            "sam_usd": population * Decimal("0.15") * 50 * Decimal("0.10"),
        }
        rounded = {k: int(v.quantize(Decimal("1"), rounding=ROUND_HALF_UP)) for k, v in unrounded.items()}
        return rounded, {k: str(v) for k, v in unrounded.items()}


def main():
    attachment = DATA / "documents/1172/US Population Census by State.csv"
    manifest = json.loads((DATA / "manifest.json").read_text())
    for source in ["data/train.csv", "documents/1172/US Population Census by State.csv"]:
        record = manifest["files"][source]
        payload = (DATA / record["local_file"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != record["sha256"]:
            raise ValueError(f"Source checksum differs from manifest: {source}")
    with attachment.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    rounded, unrounded = calculate(rows)
    with (DATA / "train.csv").open(newline="", encoding="utf-8-sig") as stream:
        task = next(r for r in csv.DictReader(stream) if r["Task ID"] == "1172")
    rubric = json.loads(task["Rubric JSON"])
    keys = {"1": "population_2032", "2": "interested_people", "3": "tam_usd", "4": "sam_usd", "6": "population_2024"}
    checks = []
    for cid, key in keys.items():
        # Explicit expected values are checked against the source rubric, not only this script.
        computed = rounded[key]
        source = rubric[f"criterion {cid}"]["description"]
        matches = f"{computed:,}" in source
        checks.append({"criterion_id": int(cid), "computed": computed, "present_in_source_rubric": matches})
        if not matches:
            raise ValueError(f"Computed value differs from rubric for criterion {cid}")
    cases = []
    for variant in ["complete", "wrong_sam", "missing_risk"]:
        nums = dict(rounded)
        if variant == "wrong_sam":
            nums["sam_usd"] += 1000000
        for language in ["en", "es"]:
            labels = {str(i): 1 for i in range(1, 7)}
            if variant == "wrong_sam":
                labels["4"] = 0
            if variant == "missing_risk":
                labels["5"] = 0
            if language == "en":
                response = (
                    "I project each state's population, including DC separately, using "
                    "P2032 = P2024 × (P2024/P2020)^2, then sum the unrounded projections. "
                    "The interested share is (0.25 + 0.20 + 0.10 + 0.05)/4 = 0.15; "
                    "TAM = P2032 × 0.15 × USD 50 and SAM = TAM × 0.10. "
                    f"Rounded results: 2024 population {nums['population_2024']}; "
                    f"2032 population {nums['population_2032']}; interested people {nums['interested_people']}; "
                    f"TAM USD {nums['tam_usd']}; SAM USD {nums['sam_usd']}."
                )
                if variant != "missing_risk":
                    response += " The 10% market-share assumption may be too optimistic because winning customers from an established competitor such as Lego can be difficult."
            else:
                response = (
                    "Proyecto la población de cada estado, incluyendo DC por separado, mediante "
                    "P2032 = P2024 × (P2024/P2020)^2 y sumo las proyecciones sin redondearlas. "
                    "La proporción interesada es (0.25 + 0.20 + 0.10 + 0.05)/4 = 0.15; "
                    "TAM = P2032 × 0.15 × USD 50 y SAM = TAM × 0.10. "
                    f"Resultados redondeados: población de 2024 {nums['population_2024']}; "
                    f"población de 2032 {nums['population_2032']}; personas interesadas {nums['interested_people']}; "
                    f"TAM USD {nums['tam_usd']}; SAM USD {nums['sam_usd']}."
                )
                if variant != "missing_risk":
                    response += " El supuesto de una participación de mercado del 10% puede ser demasiado optimista porque captar clientes de un competidor establecido como Lego puede ser difícil."
            cases.append({"pair_id": f"1172-{variant}", "language": language, "response": response,
                          "expected_labels_from_fixture_design": labels,
                          "human_review_status": "pending", "model_judgments": None})
    out = ROOT / "data/pilot"; out.mkdir(parents=True, exist_ok=True)
    payload = {
        "task_id": "1172", "status": "constructed_stimuli_not_experimental_results",
        "number_format": "Fixed ungrouped integer outputs, USD and decimal points in both languages; formatting is not varied.",
        "limitations": "Expected labels are design assumptions, not independent expert labels. This concise response is a grading stimulus, not a full expert re-solve or an agent trajectory. A bilingual domain reviewer must approve every pair before judge comparisons.",
        "original_prompt": task["Prompt"], "original_rubric": rubric, "cases": cases,
    }
    (out / "1172_matched_responses.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    report = {"task_id": "1172", "geographic_rows": len(rows), "rounded": rounded,
              "unrounded": unrounded, "rubric_checks": checks,
              "status": "five_numerical_targets_reproduced_without_an_LLM"}
    (ROOT / "analysis").mkdir(exist_ok=True)
    (ROOT / "analysis/1172_arithmetic_check.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
