#!/usr/bin/env python3
"""Write a descriptive report from completed, validated comparison results."""
import json
import csv
from pathlib import Path

import judge_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]


def main():
    data=json.loads((ROOT / "analysis/local-comparison-v1.json").read_text())
    if not data["complete"]:
        raise ValueError("Complete all planned models before writing the final report")
    models=data["models"]
    count=sum(m["valid"] for m in models)
    failures=sum(m["failed_attempts"] for m in models)
    error_rows=[]
    for model in models:
        directory=ROOT / model["run"]
        _,plan=pilot.load_run(directory)
        completed=pilot.successes(pilot.load_events(directory))
        for row in plan:
            event=completed[row["request_id"]]
            if event["result"] != row["expected_from_design"]:
                error_rows.append(dict(model=model["model"],request_id=row["request_id"],
                    task_id=row["task_id"],experiment=row["experiment"],language=row["language"],
                    expected_from_design=row["expected_from_design"],observed=event["result"],reason=event["reason"]))
    with (ROOT / "analysis/local-comparison-v1-errors.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=["model","request_id","task_id","experiment","language","expected_from_design","observed","reason"])
        writer.writeheader();writer.writerows(error_rows)
    lines=["# Comparación local de jueces — resultados observados", "",
        f"**{count}/{sum(m['planned'] for m in models)} juicios válidos**, cuatro modelos locales y tres tareas fuente seleccionadas. "
        f"Intentos fallidos registrados: {failures}. Las 108 llamadas del primer piloto son anteriores y no forman parte de este total.", "",
        "El estudio incluye 432 llamadas de replicación sobre respuestas construidas de 1172 y 648 llamadas sobre seis predicados numéricos de 1172, 2287 y 2145. "
        "Cada modelo recibe exactamente el mismo plan. Inglés–español es la comparación principal; portugués es secundario y solo aparece en los controles numéricos.", "",
        "![Errores numéricos observados](../figures/local_model_comparison.png)", "",
        "## Aplicación de tolerancias numéricas", "",
        "Una aprobación de un valor fuera del rango es un error; rechazar un valor permitido también lo es. "
        "Los denominadores cuentan juicios repetidos, no tareas independientes. Cada idioma tiene 21 juicios sobre valores incorrectos y 33 sobre valores aceptables por modelo.", "",
        "| Modelo | Idioma | Incorrectos aprobados | Aceptables rechazados |",
        "|---|---|---:|---:|"]
    for m in models:
        for r in m["rates"]:
            if r["experiment"] == "numeric_probe":
                lines.append(f"| {m['model']} | {r['language'].upper()} | {r['false_accepts']}/{r['negative_valid']} ({r['false_accept_rate']:.1%}) | {r['false_rejects']}/{r['positive_valid']} ({r['false_reject_rate']:.1%}) |")
    en=[next(r for r in m["rates"] if r["experiment"]=="numeric_probe" and r["language"]=="en") for m in models]
    totals={r["false_accepts"]+r["false_rejects"] for r in en}
    if len(en)==4 and len(totals)==1:
        lines += ["",f"**El agregado oculta fallos distintos:** los cuatro modelos cometen {next(iter(totals))}/54 errores en los controles numéricos en inglés. "
            "La distribución entre aprobaciones incorrectas y rechazos incorrectos cambia con el modelo. "
            "El resultado permite comparar perfiles de error; no basta para declarar un ganador general o atribuir toda diferencia al tamaño."]
    lines += ["", "## Diferencias entre idiomas e inestabilidad", "",
        "Se compara cada combinación respuesta × criterio. Una diferencia de tasa de aprobación no implica por sí sola que el español o el portugués sea peor evaluado: depende de si debía aprobarse esa respuesta. "
        "Las diferencias opuestas pueden cancelarse al sumar errores, por lo que también se reportan pares individuales.", "",
        "| Modelo | Bloque | Comparación | Pares con distinta aprobación | Desacuerdo entre idiomas, promedio | Desacuerdo dentro de EN / otro, promedio |",
        "|---|---|---|---:|---:|---:|"]
    for m in models:
        for block,language in [("matched_response","es"),("numeric_probe","es"),("numeric_probe","pt")]:
            rows=[c for c in m["contrasts"] if c["experiment"]==block and c["language"]==language]
            n=len(rows)
            mean=lambda k:sum(c[k] for c in rows)/n
            different=sum(abs(c["other_minus_en"])>1e-12 for c in rows)
            lines.append(f"| {m['model']} | {block} | EN/{language.upper()} | {different}/{n} | {mean('cross_language_disagreement'):.1%} | {mean('within_en_disagreement'):.1%} / {mean('within_other_disagreement'):.1%} |")
    lines += ["", "Desacuerdo entre idiomas: probabilidad empírica de etiquetas distintas al cruzar todas las combinaciones de repeticiones del par. "
        "Desacuerdo dentro del idioma: pares de repeticiones distintas de la misma celda. Son estadísticas descriptivas de esta colección; no se tratan esas combinaciones como muestras independientes.", "",
        "## Replicación de los fallos identificados en el primer piloto", "",
        "![Detalle de la replicación](../figures/local_replication_detail.png)", "",
        "Estos tres ejemplos se seleccionaron antes de ver la ampliación porque ya aparecían en el piloto inicial. El cuadro completo de 360 celdas está exportado, incluyendo resultados sin diferencias. "
        "El párrafo de riesgos se reutiliza en dos variantes: no son dos réplicas independientes del contenido.", "",
        "| Modelo | C5 riesgo presente EN / ES | C4 SAM incorrecto EN / ES | C2 número correcto EN / ES |",
        "|---|---:|---:|---:|"]
    for m in models:
        lookup={(c["pair_id"],c["criterion_id"],c["language"]):c for c in m["cells"]}
        values=[]
        for pair,cid in [("1172-complete",5),("1172-wrong_sam",4),("1172-complete",2)]:
            values.append(" / ".join(f"{lookup[(pair,cid,lang)]['passes']}/3" for lang in ["en","es"]))
        lines.append(f"| {m['model']} | {' | '.join(values)} |")
    for m in models:
        original=[r for r in m["rates"] if r["experiment"]=="matched_response"]
        if all(r["false_accepts"]==r["negative_valid"] and r["false_rejects"]==0 for r in original):
            lines += ["",f"**Concordancia sin corrección:** {m['model']} aprueba todos los criterios de todas las respuestas del bloque original, "
                "incluidas las variantes con SAM incorrecto y riesgo omitido. La concordancia EN/ES perfecta en ese bloque no implica que el juez sea fiable."]
    lines += ["", "## Alcance de las conclusiones", "",
        "- Se mide al juez, no la capacidad del modelo para resolver las tareas APEX. Las respuestas numéricas son frases construidas que contestan un criterio concreto.",
        "- Los valores de referencia provienen de las reglas publicadas. Existen cálculos independientes previos para 1172 y 2287. Durante esta ampliación también se reprodujo 2145 C1 desde 252 precios del PDF: beta 0,6079237, redondeada a 0,61. No se ha reproducido el WACC de 2145. Esta comprobación posterior no cambió el plan ni sus etiquetas; eleva a 17 los criterios numéricos reproducidos en tres tareas.",
        "- La equivalencia lingüística es intencionada y todavía no tiene revisión bilingüe independiente. Todas las rúbricas e instrucciones están en inglés. No se evaluó la localización de separadores numéricos ni un cruce de idiomas de rúbrica.",
        "- La selección de tres tareas es pequeña y deliberada. No hay intervalos poblacionales, pruebas de significancia ni afirmaciones de sesgo general de Qwen, Gemma o Mercor.",
        "- Comparar tamaños no aísla el número de parámetros de entrenamiento, plantillas o cuantización. No se evaluaron modelos frontera ni la configuración de producción de Mercor.",
        "- La prueba en portugués no valida flujos empresariales brasileños ni demuestra demanda comercial latinoamericana.", "",
        "## Archivos y siguiente etapa", "",
        "- [Protocolo y ejecución](../proposal/protocols/Experimento%20comparativo%20local.md).",
        "- [Resumen JSON completo](local-comparison-v1.json).",
        "- [Todas las celdas](local-comparison-v1-cells.csv), [contrastes](local-comparison-v1-contrasts.csv) y [tasas de error](local-comparison-v1-rates.csv).",
        "- [Todas las discrepancias con las referencias de diseño y sus explicaciones](local-comparison-v1-errors.csv). No implica que las explicaciones hayan sido anotadas por humanos.",
        "- [Verificación adicional de beta, 2145 C1](2145_beta_check.json).",
        "- Los cuatro directorios bajo `runs/local-comparison-v1/` conservan solicitudes, manifiestos, identidad de pesos y respuestas crudas.", "",
        "La siguiente etapa debe validar pares y etiquetas con revisores, incorporar nuevas familias de tareas antes de mirar sus resultados, y comparar con un juez de referencia confirmado por Mercor. "
        "Los controles actuales permiten evaluar mejoras de configuración en un estudio nuevo, manteniendo esta corrida como diagnóstico inicial.", ""]
    output=ROOT / "analysis/Comparación de modelos locales.md"
    output.write_text("\n".join(lines))
    print(output)


if __name__ == "__main__":
    main()
