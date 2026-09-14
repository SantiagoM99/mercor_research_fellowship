# Intervención numérica v1: comprobar una mejora en tareas nuevas

Este seguimiento surge de los errores observados en `local-comparison-v1`. El cambio de prompt y la selección siguiente quedan fijados antes de ejecutar estas llamadas. Es exploratorio; no constituye un prerregistro externo ni una validación independiente por expertos.

## Hipótesis y comparación

Una aclaración sobre intervalos inclusivos, tolerancias y equivalencia numérica podría reducir tanto aprobaciones incorrectas como rechazos incorrectos. Se compara el prompt público fijado con **ese mismo prompt más una única enmienda congelada**, en inglés, guardada en `experiments/prompts/numeric_clarification_v1.txt`. La enmienda no contiene respuestas, límites de estas tareas, etiquetas esperadas ni ejemplos resueltos. Es una intervención conjunta sobre instrucciones numéricas; no identifica la contribución causal de cada frase ni incluye un control de texto neutro de igual longitud.

Modelos: Qwen3 4B y Gemma3 4B, para incluir dos familias con errores observados en el estudio anterior. La selección de modelos se basa en ese diagnóstico, no es aleatoria. Se mantienen temperatura 0.01, contexto 4.096, salida máxima 512 tokens, JSON, instrucciones/rúbrica en inglés y razonamiento extendido desactivado donde corresponde. Las condiciones se intercalan en un orden aleatorio fijado, con llamadas independientes. Los dos modelos reciben el mismo plan.

## Ejemplos nuevos para nuestras corridas

| Fuente | Predicado | Nominal | Límite inferior / superior | Fuera por debajo / encima |
|---|---|---:|---|---|
| 145 C2, consultoría | Impresiones por dólar, pago de precio fijo | 9.15 | 9.05 / 9.25 | 9.04 / 9.26 |
| 1122 C1, consultoría | NPS de generación Z | -28 | -29 / -27 | -30 / -26 |
| 2205 C1, finanzas | Rendimiento al vencimiento del bono, 2025-10-01, % | 4.718 | 4.671 / 4.765 | 4.670 / 4.766 |

Son tres tareas públicas no usadas en las corridas anteriores. Se inspeccionaron sus rúbricas para construir los estímulos; no se afirma que los modelos nunca hayan visto esos datos durante entrenamiento. La selección deliberada cubre un intervalo decimal positivo, uno entero negativo y uno porcentual. No es una muestra representativa de APEX. Las cifras se mantienen idénticas entre idiomas. Las respuestas son frases que satisfacen o incumplen un predicado numérico publicado; no son entregables profesionales completos. Los blancos de estas tres tareas todavía no se han reproducido independientemente desde sus fuentes.

**360 llamadas nuevas:** tres criterios × cinco variantes × dos idiomas × tres repeticiones × dos prompts × dos modelos. Cada modelo hace 180 llamadas. Cada combinación modelo/prompt/idioma tiene 45 juicios: 27 sobre valores permitidos y 18 sobre valores fuera del intervalo.

## Análisis fijado

1. Primario: cambio en error contra el predicado publicado, desglosado por modelo, idioma y tarea. Reportar falsos rechazos y falsas aprobaciones por separado.
2. Emparejar las tasas de error de cada estímulo/idioma bajo ambos prompts. Mostrar mejoras y regresiones; no emparejar números de repetición como si compartieran una semilla de generación.
3. Como resumen complementario, contar celdas que pasan de mayoría incorrecta a correcta y viceversa. Cada celda tiene tres repeticiones; estas mayorías no son etiquetas humanas.
4. Reportar las tres tareas incluso si el promedio mejora y una empeora. No ajustar la enmienda después de ver resultados. No hacer afirmaciones poblacionales ni pruebas de significancia con tres tareas elegidas.
5. Registrar todos los intentos y tratar salidas inválidas como faltantes. Completar el plan antes de producir la gráfica final. Un fallo de transporte detiene la invocación; reanudar conserva intentos previos.

Una mejora consistente en esta colección respaldaría una candidata a calibración para validar en una muestra mayor. Una mejora parcial o regresión indicaría que la aclaración por sí sola no basta. Ningún resultado establece que una configuración esté lista para producción o que Mercor tenga el mismo problema.

## Ejecución y archivos

Con el servidor local activo:

```sh
python3 scripts/numeric_intervention.py run --model qwen3:4b
python3 scripts/numeric_intervention.py run --model gemma3:4b
python3 scripts/numeric_intervention.py report
```

Los planes ya están preparados en `runs/numeric-intervention-v1/`; `prepare` no sobrescribe. Para una réplica, usar un `--root` nuevo al preparar y ejecutar. El comando `report` escribe el resumen por defecto en `analysis/numeric-intervention-v1.json`; conservarlo antes de exportar una réplica. La configuración y el texto de la enmienda se copian al manifiesto. Su procedencia y hashes quedan fijados, junto con los del dataset y las solicitudes. La revisión lingüística independiente sigue pendiente.
