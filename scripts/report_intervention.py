#!/usr/bin/env python3
"""Report all outcomes of the completed numeric prompt intervention."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    data=json.loads((ROOT/'analysis/numeric-intervention-v1.json').read_text())
    if not data['complete']:
        raise ValueError('Complete both models before producing a final report')
    lines=['# ¿Podemos mejorar al juez en tareas nuevas?', '',
        f"Se completaron {sum(m['valid'] for m in data['models'])} juicios locales válidos. Intentos fallidos: {sum(m['failed_attempts'] for m in data['models'])}. "
        'Se comparó el prompt original con una aclaración congelada de reglas numéricas, usando Qwen 4B y Gemma 4B en tres tareas públicas no utilizadas en las corridas previas.', '',
        'La intervención indica que los extremos de los intervalos son válidos, que los valores fuera no deben aprobarse por cercanía y que el formato equivalente no autoriza cambios de valor. '
        'No incluye respuestas resueltas ni etiquetas esperadas. Los mismos estímulos se evaluaron bajo ambas condiciones, intercaladas aleatoriamente.', '',
        '![Efecto observado de la aclaración](../figures/numeric_intervention.png)', '',
        '## Resultados por modelo e idioma', '',
        'Cada condición tiene 45 juicios: 27 sobre valores aceptables y 18 sobre valores incorrectos. Se muestran todos los resultados, incluidos posibles aumentos de error.', '',
        '| Modelo | Idioma | Errores original → aclarado | Aprobaciones incorrectas original → aclarado | Rechazos incorrectos original → aclarado |',
        '|---|---|---:|---:|---:|']
    for model in data['models']:
        lookup={(r['task_id'],r['arm'],r['language']):r for r in model['rates']}
        for language in ['en','es']:
            a,b=[lookup[('all',arm,language)] for arm in ['original','clarified']]
            lines.append(f"| {model['model']} | {language.upper()} | {a['errors']}/45 → {b['errors']}/45 | {a['false_accepts']}/18 → {b['false_accepts']}/18 | {a['false_rejects']}/27 → {b['false_rejects']}/27 |")
    lines += ['', '## Transferencia por tarea', '',
        'Estos casos son nuevos para nuestras corridas; sus rúbricas públicas fueron inspeccionadas para construir los estímulos. No son datos ocultos ni una muestra aleatoria.', '',
        '| Modelo | Tarea | Idioma | Errores original → aclarado |', '|---|---|---|---:|']
    for model in data['models']:
        lookup={(r['task_id'],r['arm'],r['language']):r for r in model['rates']}
        for task in ['145','1122','2205']:
            for lang in ['en','es']:
                a,b=[lookup[(task,arm,lang)] for arm in ['original','clarified']]
                lines.append(f"| {model['model']} | {task} | {lang.upper()} | {a['errors']}/15 → {b['errors']}/15 |")
    lines += ['', '## Mejoras y regresiones por celda', '',
        'Una celda es un estímulo/idioma con tres repeticiones. Se compara la mayoría de etiquetas con el predicado de diseño. Las tasas anteriores conservan las tres llamadas; estas mayorías son un resumen complementario.', '',
        '| Modelo | Celdas de mayoría incorrecta a correcta | De correcta a incorrecta | Celdas comparadas |', '|---|---:|---:|---:|']
    for model in data['models']:
        changes=model['paired_changes']
        lines.append(f"| {model['model']} | {sum(c['repaired'] for c in changes)} | {sum(c['regressed'] for c in changes)} | {len(changes)} |")
    lines += ['', '## Interpretación', '',
        'El resultado evalúa una candidata de configuración fuera de los ejemplos que motivaron su diseño. Debe leerse por modelo, idioma y tarea: una reducción promedio no compensa automáticamente una regresión en un criterio relevante. '
        'No se ajustó la enmienda después de ver estos resultados.', '',
        'La referencia es la pertenencia al intervalo publicado. Durante la corrida se verificaron dos blancos desde los CSV: 145 C2 da 9,14544 impresiones por dólar (9,15 redondeado) y 1122 C1 da NPS -27,83505 (-28 redondeado). '
        'Esta comprobación no cambió el plan; el rendimiento del bono de 2205 sigue basado en la rúbrica. No hay revisión lingüística o profesional independiente. '
        'Son frases de un criterio, no entregables completos. Tres tareas elegidas no permiten estimar prevalencia, significancia o fiabilidad de producción. La intervención incluye varias aclaraciones y añade texto; no identifica cuál frase produce un cambio.', '',
        'El siguiente paso es validar pares y etiquetas, incorporar respuestas naturales de agentes y comparar con una configuración de referencia confirmada por Mercor. '
        'Si una candidata mejora, debe pasar por un conjunto nuevo más amplio con criterios de aceptación acordados antes de su evaluación.', '',
        '## Reproducir', '',
        '```sh', 'python3 scripts/numeric_intervention.py report',
        '.venv/bin/python scripts/plot_intervention.py', 'python3 scripts/report_intervention.py', '```', '',
        '- [Protocolo congelado](../proposal/protocols/Intervención%20numérica%20—%20protocolo.md).',
        '- [Resumen completo](numeric-intervention-v1.json), [celdas](numeric-intervention-v1-cells.csv), [tasas por tarea](numeric-intervention-v1-rates.csv), [mejoras y regresiones](numeric-intervention-v1-paired_changes.csv).',
        '- Registros: `runs/numeric-intervention-v1/`, con manifiestos, solicitudes, respuestas y hashes de pesos.',
        '']
    lines += ['- [Cálculos independientes adicionales](followup_source_checks.json).', '']
    path=ROOT/'analysis/Intervención numérica — resultados.md'
    path.write_text('\n'.join(lines))
    print(path)


if __name__=='__main__': main()
