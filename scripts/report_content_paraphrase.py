#!/usr/bin/env python3
"""Write an evidence-linked Spanish report for the completed factorial study."""
import json
from pathlib import Path
from statistics import mean

import judge_pilot as pilot

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT/'analysis/content-paraphrase-v1.json').read_text())
    if not data['complete'] or any(m['valid'] != m['planned'] for m in data['models']):
        raise ValueError('Complete both frozen model plans before writing conclusions')
    lines = [
        '# Contenido, paráfrasis e idioma: resultados locales', '',
        'Ejecución `content-paraphrase-v1`. **576 juicios válidos**, dos modelos locales, seis criterios '
        'numéricos y tres tareas públicas previamente exploradas. Las traducciones y paráfrasis '
        'no tienen revisión humana independiente. Los resultados describen controles construidos, '
        'no el desempeño profesional de agentes ni el juez de producción de APEX.', '',
        '## Resultado principal', '',
        'Cada decisión usa la mayoría de tres repeticiones. Detectar la corrección exige rechazar '
        'la respuesta incorrecta y aprobar la correcta. Cambiar por paráfrasis significa alterar '
        'la decisión con la respuesta fija. Los porcentajes promedian primero dentro de cada tarea '
        'y después entre las tres tareas. Los conteos agrupados se muestran por transparencia; '
        'su cociente no define el promedio por tarea.', '',
        '| Modelo | Respuesta | Detecta corrección, promedio por tarea | Pares detectados, agrupados | Cambia por paráfrasis, promedio por tarea | Pares cambiados, agrupados |',
        '|---|---|---:|---:|---:|---:|',
    ]
    for m in data['models']:
        for r in m['rates']:
            if r['task_id'] == 'equal_task_macro':
                lines.append(f"| {m['model']} | {r['language'].upper()} | {r['content_rate']:.1%} | "
                    f"{r['content_count']}/{r['content_pairs']} | {r['paraphrase_rate']:.1%} | "
                    f"{r['paraphrase_count']}/{r['paraphrase_pairs']} |")
    lines += ['', '![Detección de correcciones y cambios por paráfrasis](../figures/content_paraphrase.png)', '',
        'Una baja tasa de cambios por paráfrasis puede coexistir con fallos de detección. '
        'La estabilidad por sí sola no establece corrección.', '', '## Desglose por tarea', '',
        '| Modelo | Respuesta | Tarea | Detecta corrección | Cambia por paráfrasis | Cambia al evaluar en ES en vez de EN | Errores / llamadas |',
        '|---|---|---|---:|---:|---:|---:|']
    for m in data['models']:
        for r in m['rates']:
            if r['task_id'] != 'equal_task_macro':
                lines.append(f"| {m['model']} | {r['language'].upper()} | {r['task_id']} | "
                    f"{r['content_count']}/{r['content_pairs']} | {r['paraphrase_count']}/{r['paraphrase_pairs']} | "
                    f"{r['grading_language_count']}/{r['grading_language_pairs']} | {r['errors']}/{r['valid']} |")
    lines += ['', '## Idioma de evaluación y redacción', '',
        'Desglose de detección por cada combinación. El idioma de evaluación cambia rúbrica '
        'e instrucciones juntas. Un contraste entre EN y ES no separa esos dos componentes.', '',
        '| Modelo | Respuesta | Evaluación | Rúbrica | Detecta, promedio por tarea | Pares detectados, agrupados |',
        '|---|---|---|---|---:|---:|']
    for m in data['models']:
        for lang in ['en', 'es']:
            for grading in ['en', 'es']:
                for wording in ['original', 'paraphrase']:
                    pairs = [p for p in m['pairs'] if p['kind'] == 'content' and p['language'] == lang
                             and p['grading_language'] == grading and p['wording'] == wording]
                    task_means = [mean(p['detected'] for p in pairs if p['task_id'] == task) for task in ['145', '1122', '2287']]
                    lines.append(f"| {m['model']} | {lang.upper()} | {grading.upper()} | {wording} | "
                        f"{mean(task_means):.1%} | {sum(p['detected'] for p in pairs)}/{len(pairs)} |")
    lines += ['', '![Detección por criterio y condición](../figures/content_paraphrase_detail.png)', '',
        '## Corrección por llamada y repetibilidad', '',
        '| Modelo | Respuesta | Falsas aprobaciones / respuestas incorrectas | Falsos rechazos / respuestas correctas | Celdas inestables | Desacuerdo entre repeticiones, promedio por tarea |',
        '|---|---|---:|---:|---:|---:|']
    for m in data['models']:
        for r in m['rates']:
            if r['task_id'] == 'equal_task_macro':
                lines.append(f"| {m['model']} | {r['language'].upper()} | {r['false_accepts']}/{r['negative_valid']} | "
                    f"{r['false_rejects']}/{r['positive_valid']} | {r['unstable_cells']}/{r['cells']} | {r['repeat_disagreement']:.1%} |")
    lines += ['', '## Dirección de los cambios', '',
        'Conteos de pares de decisiones por mayoría; un mismo criterio puede aparecer en varias '
        'condiciones y contrastes. Estas filas no son tareas independientes y no se deben sumar '
        'para formar una tasa única.', '',
        '| Modelo | Cambio | Pares comparados | Cambios de mayoría | Corrigen error | Introducen error | Cambian fracción de aprobaciones |',
        '|---|---|---:|---:|---:|---:|---:|']
    names = {'paraphrase': 'Original → paráfrasis', 'grading_language': 'Evaluación EN → ES',
             'response_language': 'Respuesta EN → ES'}
    for m in data['models']:
        for kind, label in names.items():
            pairs = [p for p in m['pairs'] if p['kind'] == kind]
            lines.append(f"| {m['model']} | {label} | {len(pairs)} | {sum(p['changed'] for p in pairs)} | "
                f"{sum(p['repaired'] for p in pairs)} | {sum(p['regressed'] for p in pairs)} | {sum(p['fraction_changed'] for p in pairs)} |")
    lines += ['', 'Todos los contrastes, incluidos los ceros, están en '
        '[el CSV de pares](content-paraphrase-v1-pairs.csv). La variación de fracciones se reporta '
        'aunque no cambie la mayoría; debe leerse junto a la inestabilidad de repeticiones idénticas.', '',
        '## Casos que cambian con la paráfrasis', '',
        '| Modelo | Tarea / criterio | Estado | Respuesta | Evaluación | Original → paráfrasis | Efecto |',
        '|---|---|---|---|---|---|---|']
    changed_count = 0
    for m in data['models']:
        for p in m['pairs']:
            if p['kind'] == 'paraphrase' and p['changed']:
                changed_count += 1
                lines.append(f"| {m['model']} | {p['task_id']} / C{p['criterion_id']} | {p['state']} | "
                    f"{p['language'].upper()} | {p['grading_language'].upper()} | {p['before']} → {p['after']} | "
                    f"{'Corrige' if p['repaired'] else 'Introduce error'} |")
    if not changed_count:
        lines += ['| — | — | — | — | — | — | No hubo cambios de mayoría |']
    lines += ['', '## Lectura para la propuesta', '']
    for m in data['models']:
        errors = sum(c['errors'] for c in m['cells'])
        paraphrase = [p for p in m['pairs'] if p['kind'] == 'paraphrase']
        response = [p for p in m['pairs'] if p['kind'] == 'response_language']
        grading = [p for p in m['pairs'] if p['kind'] == 'grading_language']
        lines += [f"**{m['model']}:** {errors}/{m['valid']} juicios difieren de la regla numérica. "
            f"Cambian por paráfrasis {sum(p['changed'] for p in paraphrase)}/{len(paraphrase)} pares, "
            f"por idioma de respuesta {sum(p['changed'] for p in response)}/{len(response)} "
            f"y por idioma de evaluación {sum(p['changed'] for p in grading)}/{len(grading)}.", '']
    lines += ['El aporte de este bloque es comprobar conjuntamente sensibilidad y estabilidad. '
        'Si un modelo conserva errores al reformular o traducir, esa consistencia no valida '
        'la evaluación. Si otro acierta estos controles, ese resultado debe conservarse '
        'aunque no apoye una hipótesis de sensibilidad lingüística.', '',
        'Los fallos del estudio numérico anterior y el resultado de este bloque corresponden '
        'a conjuntos distintos. En particular, en 1122 el Qwen anterior rechazaba los extremos '
        'permitidos -29 y -27; este bloque utiliza -28 y -30. No interpretar una mejor tasa aquí '
        'como mejora causal por paráfrasis, entrenamiento o adaptación: cambiaron los valores probados. '
        'Ver [intervención anterior](Intervención%20numérica%20—%20resultados.md).', '',
        '## Ejemplos auditables de errores', '',
        'Se muestra el primer error observado de cada modelo, si existe, en el orden de ejecución. '
        'Es un ejemplo ilustrativo; las tasas anteriores incluyen todos los casos.', '']
    for m in data['models']:
        directory = ROOT/'runs/content-paraphrase-v1'/m['model'].replace(':', '-')
        _, plan = pilot.load_run(directory)
        by_id = {r['request_id']: r for r in plan}
        examples = [(by_id[e['request_id']], e) for e in pilot.load_events(directory)
                    if e['status'] == 'ok' and e['result'] != by_id[e['request_id']]['expected_from_design']]
        if examples:
            r, e = examples[0]
            lines += [f"**{m['model']} — `{r['request_id']}`**", '',
                f"Criterio: {r['criterion']}", '', f"Respuesta: {r['response']}", '',
                f"Veredicto del modelo: {e['result']}; etiqueta de construcción: {r['expected_from_design']}.", '',
                f"Explicación registrada: {e['reason']}", '']
        else:
            lines += [f"**{m['model']}:** ningún error observado en este bloque.", '']
    failed = sum(m['failed_attempts'] for m in data['models'])
    lines += ['', '## Alcance y trazabilidad', '',
        f'- 576/576 llamadas válidas; {failed} intentos fallidos registrados.',
        '- Tres tareas elegidas de forma deliberada, con cuatro criterios en 2287 y uno en cada otra tarea. '
        'Los porcentajes macro asignan el mismo peso a las tres tareas.',
        '- Una sola paráfrasis conservadora por criterio e idioma; no representa todas las formas de redactar una rúbrica.',
        '- Los controles correctos usan el nominal y los incorrectos un valor fuera del rango. '
        'Este estudio no vuelve a probar todos los extremos de tolerancia del estudio anterior.',
        '- Ocho de las 96 combinaciones de estímulos por modelo reutilizan exactamente prompts '
        'del estudio numeric-intervention-v1 (145 y 1122, instrucciones EN y rúbrica original). '
        'Son nuevas llamadas sobre controles conocidos, no nuevos ejemplos independientes.',
        '- Los modelos se ejecutaron secuencialmente, Qwen primero. Las condiciones dentro de cada modelo '
        'se intercalaron en un orden fijado antes de la inferencia.',
        '- No se ha realizado revisión humana independiente ni inferencia poblacional; '
        'las diferencias no establecen un sesgo lingüístico general.', '',
        'El siguiente paso de validación es revisar equivalencia y adecuación de las respuestas '
        'y repetir el diagnóstico sobre una configuración de referencia confirmada con Mercor '
        'y respuestas profesionales naturales. Los datos actuales permiten localizar fallos y '
        'formular esa solicitud; no elegir una configuración de producción.', '',
        'Archivos: [protocolo](../proposal/protocols/Contenido%20y%20paráfrasis%20—%20protocolo.md), '
        '[análisis completo](content-paraphrase-v1.json), [celdas](content-paraphrase-v1-cells.csv), '
        '[tasas](content-paraphrase-v1-rates.csv), '
        '[estímulos congelados Qwen](../runs/content-paraphrase-v1/qwen3-4b/requests.jsonl), '
        '[resultados crudos Qwen](../runs/content-paraphrase-v1/qwen3-4b/results.jsonl), '
        '[resultados crudos Gemma](../runs/content-paraphrase-v1/gemma3-4b/results.jsonl).', '']
    path = ROOT/'analysis/Contenido y paráfrasis — resultados.md'
    path.write_text('\n'.join(lines))
    print(path)


if __name__ == '__main__':
    main()
