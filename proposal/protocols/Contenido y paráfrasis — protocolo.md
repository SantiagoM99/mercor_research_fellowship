# Contenido y paráfrasis: protocolo de ejecución

Diseño congelado el 13 de septiembre de 2026 en `runs/content-paraphrase-v1/*/manifest.json`, antes de la inferencia. El archivo de configuración, las solicitudes completas, las plantillas y el código de preparación tienen huellas SHA-256. Los resultados y la identidad del modelo se guardan por llamada; el servidor es Ollama local, sin API de pago.

## Pregunta y alcance

¿El juez aprueba una respuesta correcta y rechaza su contraparte incorrecta? ¿Conserva su decisión cuando únicamente se reformula la rúbrica? ¿Cómo cambian ambos comportamientos con el idioma de la respuesta y de la evaluación?

Esta es una exploración de desarrollo sobre tres tareas públicas ya inspeccionadas. No es una evaluación de agentes resolviendo tareas, un estudio sobre el juez de producción de Mercor ni una estimación representativa de APEX. Las respuestas son fragmentos numéricos construidos. La corrección se define por la regla publicada y los cálculos reproducidos; la revisión independiente de equivalencia y adecuación de los fragmentos sigue pendiente.

## Estímulos y selección

| Tarea / criterio | Concepto | Correcto | Incorrecto | Rango publicado |
|---|---|---:|---:|---|
| 145 / C2 | Impresiones por dólar, precio fijo | 9.15 | 9.26 | 9.05–9.25 |
| 1122 / C1 | NPS, generación Z | -28 | -30 | -29 a -27 |
| 2287 / C1 | TIR | 17.9% | 18.1% | 17.8–18.0% |
| 2287 / C2 | MOIC | 1.5x | 1.3x | 1.4–1.6x |
| 2287 / C5 | VPN al 20% | -2.3 millones | -2.5 millones | -2.4 a -2.2 millones |
| 2287 / C3 | VPN al 10% | 10.9 millones | 11.1 millones | 10.8–11.0 millones |

Los cálculos base se reproducen usando los adjuntos públicos de las tareas. El valor correcto es el nominal publicado, coincidente con el cálculo redondeado para los seis criterios elegidos. En preparación se consideró C6 de 2287: su cálculo redondeado es 2.8 y el nominal 2.9, ambos dentro del rango. Se eligió C3 antes de congelar o consultar a los jueces para mantener la coincidencia entre nominal y cálculo redondeado en todo el conjunto. No hubo selección basada en resultados de esta ejecución.

Las paráfrasis son conservadoras: cambian el orden sintáctico de la primera oración y mantienen el rango literalmente dentro de cada idioma. Los acrónimos técnicos se traducen cuando corresponde: IRR/TIR y NPV/VPN. Los números usan la misma notación decimal en EN y ES; el experimento no mide localización de separadores. No se añade la aclaración numérica del estudio anterior.

## Matriz y configuración

6 criterios × 2 estados de corrección × 2 idiomas de respuesta × 2 idiomas de evaluación × 2 redacciones × 2 modelos × 3 repeticiones = **576 llamadas**, 288 por modelo.

Los modelos son `qwen3:4b` y `gemma3:4b`; sus pesos, cuantización y versión de servidor quedan registrados en `runtime_identity.json`. Cada modelo usa un proceso secuencial; Qwen se ejecuta antes que Gemma. Las condiciones se intercalan con semilla de orden `20260913`, idéntica entre modelos. La comparación entre modelos no está aislada de posibles efectos temporales del equipo.

Temperatura 0.01, `think=false`, contexto 4096, salida máxima 512 tokens, `top_p=0.95`, `top_k=20`, penalización de repetición 1.0. No se fija semilla de muestreo del servidor; las repeticiones estiman inestabilidad bajo esta configuración. Cada llamada recibe un único mensaje independiente con criterio y respuesta, y devuelve JSON binario más una explicación. Las etiquetas de construcción y la identidad de la condición no se incluyen en el mensaje.

El idioma de evaluación cambia conjuntamente las instrucciones y la rúbrica. La paráfrasis cambia solo la rúbrica dentro del idioma. Por ello, el contraste EN/ES de evaluación no identifica por separado el efecto de traducir las instrucciones y el criterio. La condición original EN conserva exactamente la plantilla pública fijada en el repositorio. La plantilla ES conserva las claves JSON `result` y `reason`.

Los errores de infraestructura o salida inválida quedan como faltantes y pueden reintentarse sin repetir respuestas válidas. La figura final requiere las 576 respuestas válidas. Se conserva todo intento fallido. Nunca convertir un error de transporte o parseo en un criterio incumplido.

## Análisis fijado antes de la inferencia

Cada celda combina criterio, corrección, idioma de respuesta, idioma de evaluación y redacción. Tres repeticiones producen una decisión por mayoría; hay 96 celdas por modelo.

**Detección de corrección:** un par cuenta solo si la respuesta incorrecta recibe 0 y la correcta recibe 1. Aprobar ambas, rechazar ambas o invertir los veredictos cuenta como fallo de detección. Hay 48 pares por modelo, 24 por idioma de respuesta al combinar idiomas de evaluación y redacciones.

**Cambio por paráfrasis:** comparar las mayorías original/paráfrasis con la misma respuesta y el mismo idioma de evaluación. Registrar además si cada cambio corrige o introduce un error. Hay 48 pares por modelo, 24 por idioma de respuesta.

**Idioma de evaluación y de respuesta:** contrastes emparejados con las demás variables fijas. Reportar cambios de mayoría y diferencias en fracción de aprobaciones. Estos son diagnósticos sobre estímulos sin revisión humana independiente; no se denominan sesgo lingüístico demostrado.

Promediar primero dentro de tarea y después entre las tres tareas, con igual peso por tarea. Mostrar también conteos sin ponderar: 2287 aporta cuatro criterios y cada otra tarea uno, por lo que un porcentaje macro puede diferir de la razón entre los conteos agrupados. Desglosar por tarea e idioma de evaluación. No tratar 576 llamadas ni seis criterios como 576 o seis tareas independientes.

Como complemento, reportar falsos positivos/negativos por llamada, celdas inestables y desacuerdo entre repeticiones idénticas. Para n repeticiones con p aprobaciones, el desacuerdo entre pares distintos es `2p(n-p)/(n(n-1))`. Las diferencias entre condiciones se informan también mediante fracciones de aprobación para que la mayoría no oculte variación. No presentar intervalos poblacionales ni pruebas de significación con estas tres tareas seleccionadas.

## Reproducción

```sh
python3 -m unittest discover -s tests -q
python3 scripts/content_paraphrase.py prepare --root runs/content-paraphrase-reproduction
python3 scripts/content_paraphrase.py run --root runs/content-paraphrase-reproduction --model qwen3:4b
python3 scripts/content_paraphrase.py run --root runs/content-paraphrase-reproduction --model gemma3:4b
```

`prepare` rechaza directorios existentes. `run` reanuda únicamente solicitudes sin resultado válido y rechaza cambios de identidad del modelo o configuración. El parámetro `--max-calls` limita intentos por invocación, no el total del estudio.

Para reconstruir los informes de la ejecución original:

```sh
python3 scripts/content_paraphrase.py report
python3 scripts/report_content_paraphrase.py
python3 scripts/plot_content_paraphrase.py
python3 scripts/verify_content_results.py
```

La figura usa las dependencias de `requirements-figures.txt`. No sustituir los resultados originales por una reproducción: el comando `report` escribe los nombres canónicos de análisis del estudio. Conservar por separado los informes de cualquier nueva ejecución.

El paquete de revisión contiene 36 pares para equivalencia y 96 ítems individuales para calificación, sin resultados de los modelos. Se exporta con `python3 scripts/export_content_review.py`, que rechaza sobrescribir una carpeta existente. El verificador final contrasta los resultados crudos con las métricas regeneradas, comprueba identidad, integridad de entradas y presupuesto de contexto, y escribe `analysis/content-paraphrase-v1-artifacts.json`.
