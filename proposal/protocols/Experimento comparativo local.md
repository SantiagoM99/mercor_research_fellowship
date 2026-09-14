# Experimento comparativo local v1

Plan fijado el 12 de septiembre de 2026 antes de observar resultados de esta ampliación. Es un estudio exploratorio posterior al primer piloto, no un prerregistro externo ni una muestra confirmatoria independiente. Configuración: `experiments/local-comparison-v1.json`.

## Preguntas y alcance

1. ¿El patrón observado en las respuestas completas de 1172 reaparece al cambiar de juez?
2. ¿Los jueces aceptan valores dentro de los intervalos publicados y rechazan valores fuera de ellos?
3. ¿Cambian las etiquetas entre inglés y español manteniendo números y contenido pretendidamente equivalentes? Portugués es una exploración secundaria limitada a los controles numéricos.

Cuatro modelos locales: Qwen3 1.7B, 4B y 8B, y Gemma3 4B. Son tamaños nominales de los tags, con pesos y metadatos exactos registrados por corrida. Los tres Qwen permiten comparar tamaños dentro de la misma familia; Gemma añade otra familia. Sus plantillas y entrenamiento difieren: el tamaño no queda aislado como única causa. Todos se ejecutan con temperatura 0.01, salida JSON, máximo 512 tokens y contexto de 4.096 tokens. Qwen usa `think: false`; Gemma3 no tiene el mismo modo de razonamiento extendido. Estas configuraciones no representan el rendimiento óptimo de cada modelo ni a los jueces de producción de Mercor.

Catálogos consultados: [Qwen 4B](https://ollama.com/library/qwen3:4b), [Qwen 8B](https://ollama.com/library/qwen3:8b), [Gemma 4B](https://ollama.com/library/gemma3:4b). Las descargas no constituyen llamadas a APIs de inferencia.

## Diseño congelado

| Bloque | Contenido | Llamadas por juez |
|---|---|---:|
| Replicación del piloto | 1172: tres respuestas × dos idiomas × seis criterios × tres repeticiones | 108 |
| Controles numéricos | Seis criterios de tres tareas × tres variantes × tres idiomas × tres repeticiones | 162 |
| Total | Mismas solicitudes y mismo orden aleatorio para los cuatro jueces | 270 |

Se harán **1.080 llamadas nuevas**. Las 108 previas quedan archivadas y no se combinan como si fueran tareas adicionales. Se ejecuta un modelo a la vez para evitar competencia por memoria; el orden de modelos no está aleatorizado. Cada llamada tiene contexto independiente y las contrapartes no se muestran juntas. Se registran todas las respuestas, errores y versiones. Los errores de ejecución o salidas truncadas son datos faltantes, nunca etiquetas negativas. Un reintento conserva el error anterior; los resultados completos se reanudan sin repetirse.

| Tarea y criterio | Variantes numéricas, en el orden del diseño | Referencia |
|---|---|---|
| 1172 C2: personas interesadas | 53806553, 53806554, 53806555 | Primeras dos dentro de [53806552, 53806554] |
| 1172 C4: SAM, USD | 269032763, 269032764, 270032763 | Solo el primer valor cumple el valor exacto |
| 2287 C5: NPV, millones USD | -2.3, -2.4, -2.5 | Primeras dos dentro de [-2.4, -2.2] |
| 2287 C6: venta, millones USD | 2.9, 2.8, 2.7 | Primeras dos dentro de [2.8, 3.0] |
| 2145 C1: beta | 0.61, 0.60, 0.59 | Primeras dos dentro de [0.60, 0.62] |
| 2145 C10: WACC, % | 8.8, 8.7, 8.6 | Primeras dos dentro de [8.7, 8.9] |

Se mantienen cifras idénticas entre idiomas: sin separador de miles y con punto decimal. No se prueba localización numérica en esta fase. Cada control numérico contiene una frase que responde a un único criterio; **no es una solución completa de la tarea**. La rúbrica e instrucciones permanecen en inglés, conforme a la plantilla pública fijada. El juez recibe solo descripción del criterio y respuesta.

1172 y 2287 cuentan con cálculos independientes previos. Los valores de 2145 se toman de la rúbrica pública para comprobar su aplicación; no se ha reproducido independientemente su modelo financiero. La selección es deliberada y pequeña: los seis criterios y las tres variantes no son observaciones independientes del universo APEX.

## Análisis fijado

- Informar aprobaciones incorrectas entre los controles fuera del rango y rechazos incorrectos entre los controles dentro del rango, separados por modelo, idioma, tarea y criterio. En los controles numéricos hay 21 juicios negativos de diseño y 33 positivos por idioma y juez.
- Comparar tasas de aprobación EN/ES y, secundariamente, EN/PT sobre cada par. Informar también desacuerdo entre todas las combinaciones de repeticiones de ambos idiomas y desacuerdo dentro de cada idioma.
- Mostrar todos los modelos y todas las celdas en archivos exportables. No seleccionar solo ejemplos con brechas. La figura principal muestra errores numéricos por idioma; un detalle adicional puede retomar los tres fallos identificados antes de esta ampliación: 1172 C5 en respuesta completa, C4 con SAM incorrecto y C2 en respuesta completa.
- No reportar intervalos de confianza poblacionales, significancia o prevalencia sobre APEX con tres tareas seleccionadas. Concordancia entre idiomas no equivale a corrección; una tasa de aprobación baja tampoco equivale automáticamente a peor calidad del agente.

Las etiquetas son referencias de diseño respaldadas por predicados numéricos, **no anotaciones humanas independientes**. La revisión bilingüe y profesional sigue pendiente. No ajustar prompts para mejorar una cifra dentro de esta corrida. Cualquier intervención posterior debe recibir otro ID de estudio y conservar este resultado inicial.

## Ejecución

Con el servidor del proyecto activo (`python3 scripts/qwen_local.py serve`), descargar los modelos adicionales con `OLLAMA_HOST=127.0.0.1:11434 ollama pull <modelo>`. La ubicación de pesos la establece el servidor: `.models/ollama/`.

Los cuatro planes ya están preparados bajo `runs/local-comparison-v1/`. Para ejecutarlos o reanudar pendientes, uno a la vez:

```sh
python3 scripts/model_comparison.py run --model qwen3:1.7b
python3 scripts/model_comparison.py run --model qwen3:4b
python3 scripts/model_comparison.py run --model qwen3:8b
python3 scripts/model_comparison.py run --model gemma3:4b
python3 scripts/model_comparison.py report
```

La ejecución devuelve código 2 cuando aún hay resultados pendientes; cada invocación está limitada a 270 intentos. Para una réplica nueva: `python3 scripts/model_comparison.py prepare --root runs/local-comparison-replica`, y usar ese `--root` al ejecutar y resumir. Los planes existentes nunca se sobrescriben. El archivo de configuración se copia al manifiesto para que una edición posterior del archivo fuente no cambie una corrida ya congelada.
