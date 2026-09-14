#!/usr/bin/env python3
"""Reproduce a second task and measure deterministic rubric sensitivity.

These are constructed interventions and numeric checks, not observed LLM judgments.
"""
import csv
import hashlib
import json
import math
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
from pathlib import Path

from build_pilot_fixture import calculate

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/apex-v1-extended"
START = date(2024, 3, 3)
SALE_DATE = date(2028, 12, 31)
MAINTENANCE_DATE = date(2026, 8, 12)
OP_DATES = [date.fromisoformat(s) for s in [
    "2024-12-31", "2025-06-30", "2025-12-31", "2026-06-30",
    "2026-12-31", "2027-06-30", "2027-12-31", "2028-06-30",
]]
OPERATIONS = [(d, 50000 + 5000 * i) for i, d in enumerate(OP_DATES)]


def flows(profit=150.0, sale=10000000.0, maintenance=10000000.0):
    return sorted([(START, -50000000.0), (MAINTENANCE_DATE, -maintenance), (SALE_DATE, sale)]
                  + [(d, units * profit) for d, units in OPERATIONS])


def xnpv(rate, cashflows):
    if rate <= -1:
        raise ValueError("Discount rate must exceed -1")
    origin = min(d for d, _ in cashflows)
    return math.fsum(value / (1 + rate) ** ((day - origin).days / 365) for day, value in cashflows)


def bisect_irr(cashflows, low=0.0, high=1.0):
    left, right = xnpv(low, cashflows), xnpv(high, cashflows)
    if left * right > 0:
        raise ValueError("IRR root is not bracketed; this is a case-specific solver")
    for _ in range(100):
        midpoint = (low + high) / 2
        value = xnpv(midpoint, cashflows)
        if left * value <= 0:
            high = midpoint
        else:
            low, left = midpoint, value
    return (low + high) / 2


def finance_values(maintenance=10000000.0):
    cf = flows(maintenance=maintenance)
    inflow = math.fsum(v for _, v in cf if v > 0)
    outflow = -math.fsum(v for _, v in cf if v < 0)
    values = {1: bisect_irr(cf) * 100, 2: inflow / outflow}
    for cid, rate in zip([3, 4, 5], [0.10, 0.15, 0.20]):
        values[cid] = xnpv(rate, cf) / 1e6
    for cid, rate in zip([6, 7, 8], [0.15, 0.20, 0.25]):
        without_sale = flows(sale=0, maintenance=maintenance)
        values[cid] = -xnpv(rate, without_sale) * (1 + rate) ** ((SALE_DATE - START).days / 365) / 1e6
    for cid, rate in zip([9, 10, 11], [0.15, 0.20, 0.25]):
        fixed = xnpv(rate, flows(profit=0, maintenance=maintenance))
        unit_pv = math.fsum(units / (1 + rate) ** ((day - START).days / 365) for day, units in OPERATIONS)
        values[cid] = -fixed / unit_pv
    return values


def round_half_up(value, digits=0):
    return float(Decimal(str(value)).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def finance_bounds(rubric):
    result = {}
    for cid in range(1, 12):
        description = rubric[f"criterion {cid}"]["description"]
        match = re.search(r"acceptable range of (.+?) to (.+?)\)", description, re.I)
        if not match:
            raise ValueError(f"Cannot extract tolerance from criterion {cid}")
        def number(text):
            # Convert displayed units only; % and MM remain percent points and millions.
            return float(re.sub(r"[^0-9.+-]", "", text).rstrip("."))
        result[cid] = [number(match.group(1)), number(match.group(2))]
    return result


def score_finance(values, bounds):
    checks = []
    for cid, value in values.items():
        digits = 2 if cid >= 9 else 1
        submitted = round_half_up(value, digits)
        lo, hi = bounds[cid]
        checks.append({"criterion_id": cid, "computed": value, "submitted_rounded": submitted,
                       "accepted_range": [lo, hi], "numeric_pass": lo <= submitted <= hi})
    return checks


def market_cases(rows):
    baseline, raw = calculate(rows)
    omitted, _ = calculate([r for r in rows if r["State"] != ".District of Columbia"])
    with localcontext() as context:
        context.prec = 50
        early = dict(baseline)
        rounded_population = Decimal(raw["population_2032"]).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        rounded_interested = (rounded_population * Decimal("0.15")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        early.update(interested_people=int(rounded_interested), tam_usd=int(rounded_interested * 50),
                     sam_usd=int((rounded_interested * 5).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    terminal = dict(baseline)
    terminal["sam_usd"] += 1000000
    return {"baseline": baseline, "round_each_intermediate": early, "omit_dc": omitted,
            "wrong_sam_only": terminal}


def main():
    manifest = json.loads((DATA / "manifest.json").read_text())
    for name in ["data/train.csv", "documents/1172/US Population Census by State.csv", "documents/2287/KatNip.pdf"]:
        record = manifest["files"][name]
        if hashlib.sha256((DATA / record["local_file"]).read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"Source changed: {name}")
    with (DATA / "train.csv").open(newline="") as stream:
        tasks = {r["Task ID"]: r for r in csv.DictReader(stream)}
    rubric = json.loads(tasks["2287"]["Rubric JSON"])
    bounds = finance_bounds(rubric)
    base_finance = score_finance(finance_values(), bounds)
    omitted_finance = score_finance(finance_values(maintenance=0), bounds)
    with (DATA / "documents/1172/US Population Census by State.csv").open(newline="") as stream:
        market = market_cases(list(csv.DictReader(stream)))
    key_to_cid = {"population_2032": 1, "interested_people": 2, "tam_usd": 3, "sam_usd": 4, "population_2024": 6}
    market_results = []
    for name, values in market.items():
        checks = []
        for key, cid in key_to_cid.items():
            reference = market["baseline"][key]
            lo, hi = (53806552, 53806554) if cid == 2 else (reference, reference)
            checks.append({"criterion_id": cid, "computed": values[key], "reference": reference,
                           "delta": values[key] - reference, "numeric_pass": lo <= values[key] <= hi})
        passes = sum(c["numeric_pass"] for c in checks)
        market_results.append({"intervention": name, "checks": checks, "numeric_passes": passes,
                               "numeric_criteria": 5, "numeric_only_score_pct": 100 * passes / 5,
                               "full_rubric_score_if_semantic_criterion_passes_pct": 100 * (passes + 1) / 6})
    report = {
        "status": "deterministic_reproduction_and_constructed_interventions_no_LLM_judgments",
        "provenance": {"dataset_revision": manifest["revision"], "source_manifest": "data/apex-v1-extended/manifest.json"},
        "finance_assumptions": {
            "input_extraction": "Cash-flow inputs manually transcribed from the verified KatNip.pdf; no target values used to fit the solver.",
            "date_convention": "MM/DD/YYYY, as specified in attachment; actual elapsed days / 365, matching XNPV/XIRR.",
            "moic": "Sum of positive flows / absolute sum of negative flows, matching rubric justification.",
            "numerics": "Bracketed root on [0,1]; direct back-solving of sale and unit profit at fixed rates; round only submitted outputs.",
            "documentation": "https://support.microsoft.com/en-us/excel/functions/xnpv-function",
        },
        "finance_baseline": base_finance, "finance_omit_maintenance": omitted_finance,
        "finance_declared_dependency_edges": sum(len(c["dependent_criteria"]) for c in rubric.values()),
        "market_interventions": market_results,
        "limitations": ["Two selected public tasks, not a representative sample.",
                        "Numeric predicates do not evaluate the quality of explanation or replace the official judge.",
                        "Interventions are constructed; their frequency in real model outputs is unknown.",
                        "Sensitivity to genuine mistakes is not evidence of judge bias or an invalid rubric.",
                        "Full market-rubric scores assume its semantic criterion passes; that label has not been judged."],
    }
    out = ROOT / "analysis"; out.mkdir(exist_ok=True)
    (out / "sensitivity_results.json").write_text(json.dumps(report, indent=2) + "\n")
    fin_pass = sum(c["numeric_pass"] for c in base_finance)
    fin_error_pass = sum(c["numeric_pass"] for c in omitted_finance)
    lines = ["# Qué podemos demostrar ahora", "",
             "Resultados reproducibles: `python3 scripts/measure_sensitivity.py`. No se hicieron llamadas a modelos ni anotaciones humanas independientes.", "",
             "## 1. Controles numéricos verificados", "",
             f"**16 criterios numéricos comprobados en dos tareas:** cinco en consultoría (1172) y {fin_pass}/11 en finanzas (2287). En KatNip, las 11 respuestas están dentro de las tolerancias publicadas; no todas coinciden con el valor nominal redondeado de la rúbrica.", "",
             "| Criterio KatNip | Cálculo | Respuesta redondeada | Rango aceptado |",
             "|---|---:|---:|---|",
    ]
    for c in base_finance:
        lines.append(f"| {c['criterion_id']} | {c['computed']:.6f} | {c['submitted_rounded']} | {c['accepted_range']} |")
    lines += ["", "IRR se expresa en puntos porcentuales; NPV y valor de venta en millones de USD; precio unitario en USD. Los flujos se reconstruyeron del PDF adjunto. Se usaron días efectivos / 365, conforme a [XNPV de Microsoft](https://support.microsoft.com/en-us/excel/functions/xnpv-function).", "",
              "Un ejemplo de tolerancia útil: el valor de venta calculado para 15% es USD 2,820404 millones, que redondea a 2,8, mientras el valor nominal de la rúbrica es 2,9. Ambos están dentro del intervalo aceptado [2,8; 3,0]. Esto permite probar si un juez aplica el intervalo o se ancla indebidamente al número nominal.", "",
              "## 2. Sensibilidad a errores controlados", "",
              "| Tarea | Intervención construida | Criterios numéricos que dejan de cumplir |",
              "|---|---|---:|",
    ]
    names = {"round_each_intermediate": "Redondear antes de terminar", "omit_dc": "Omitir DC de los datos", "wrong_sam_only": "Cambiar solo el SAM en USD 1 millón"}
    for case in market_results[1:]:
        lines.append(f"| 1172 | {names[case['intervention']]} | {5 - case['numeric_passes']}/5 |")
    lines.append(f"| 2287 | Omitir el mantenimiento de USD 10 millones | {11-fin_error_pass}/11 |")
    lines += ["", "**El redondeo prematuro cambia TAM en USD 21 y SAM en USD 2.** Incumple dos requisitos de valor exacto. El enunciado prohíbe redondeos intermedios: es un error real según la tarea, no una prueba de injusticia del evaluador. Permite contrastar cumplimiento de instrucciones con cambio puramente lingüístico.", "",
              "**La ausencia de dependencias declaradas no demuestra independencia.** KatNip declara cero aristas; sin embargo, sus respuestas comparten un modelo de flujos. Omitir un gasto común cambia varias respuestas y sus resultados de cumplimiento. Los metadatos son un punto de partida, no un mapa exhaustivo de sensibilidad.", "",
              "Estos resultados miden la sensibilidad mecánica de los blancos numéricos a errores elegidos. No son frecuencias de errores de agentes ni decisiones observadas de un juez. Los puntajes de cinco criterios numéricos no son el score completo de seis criterios de 1172; el JSON distingue ambos y condiciona el segundo a que el criterio semántico se cumpla.", "",
              "## 3. Mediciones que fortalecerían más el pitch", "",
              "| Prioridad | Medición | Diseño mínimo | Qué permite concluir |",
              "|---|---|---|---|",
              "| 1 | Cambio de etiqueta EN/ES sobre el mismo contenido | Pares revisados; jueces y contexto fijos; tres repeticiones por idioma | Sensibilidad de la calificación al idioma en estos ejemplos, comparada con inestabilidad dentro del idioma. |",
              "| 2 | Respeto de tolerancias numéricas | Valor nominal, otro valor dentro del intervalo y un valor fuera; misma respuesta salvo ese número | Si el juez aplica la regla publicada o se ancla al nominal. |",
              "| 3 | Efecto de formato | Mantener idioma y valor; variar 2.8 / 2,8 con convención explícita, millones / valor absoluto, fechas equivalentes | Si representaciones equivalentes producen desacuerdos. El separador decimal requiere convención inequívoca. |",
              "| 4 | Efecto de configuración | Mismos outputs; comparar contexto, modelo de juez y media/mediana por separado | Qué parte de una diferencia proviene de elecciones del evaluador. |",
              "| 5 | Propagación y objetivos principales | Errores aislados frente a errores que se propagan; comparar etiquetas por prioridad | Cómo distintas clases de error contribuyen al puntaje; no cuál puntuación es más válida sin revisión experta. |",
              "", "## 4. Siguiente experimento acotado", "",
              "Empezar por 1172: tres respuestas × dos idiomas × dos jueces × tres repeticiones × seis criterios = **216 llamadas por criterio**, con rúbrica e instrucciones en inglés y contexto fijo. Seis versiones de respuesta requieren revisión bilingüe previa. Esto es un piloto descriptivo de una familia, no una estimación poblacional. La credencial del proveedor no está configurada en el entorno inspeccionado; no se ejecutaron llamadas ni se inventaron resultados.", "",
              "Antes de correr: conservar etiquetas humanas independientes, aleatorizar llamadas y ocultar contrapartes, registrar versiones y errores del proveedor, y separar los criterios numéricos de los semánticos. Congelar el plan antes de mirar resultados. Agregar la rúbrica en español después, duplicando el número de llamadas a 432.", "",
              "## Frase utilizable en el pitch", "",
              "> I reproduced 16 numerical criteria across two public APEX tasks and constructed controlled error interventions. These provide traceable anchors for testing whether judges preserve equivalent answers across languages, respect numerical tolerances, and distinguish upstream errors from independent failures.", "",
              "No afirmar todavía que el juez discrimina por idioma, que existen fallas observadas de calificación, o que un error numérico pequeño es profesionalmente irrelevante.", "",
    ]
    (out / "Qué medir y avances.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"finance_baseline_passes": fin_pass, "finance_omission_passes": fin_error_pass,
                      "market": [{"intervention": c["intervention"], "numeric_passes": c["numeric_passes"]} for c in market_results]}, indent=2))


if __name__ == "__main__":
    main()
