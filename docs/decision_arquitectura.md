# Decisión de arquitectura: elección de modelo

Fecha de comparación: 22 de octubre de 2026  
Nombre de la miniaplicación: Asistente HCP (nombre propuesto)

## Modelo elegido

Elegí provisionalmente el modelo `gemini-3.5-flash-lite`.

Mi miniaplicación sirve para responder consultas introductorias sobre la huella de carbono de productos.

Los requisitos que necesito cumplir son:

- Entregar respuestas claras y técnicamente pertinentes.
- Mantener una latencia promedio inferior a 5 segundos.
- Equilibrar costo, rapidez y calidad, gestionando los errores del servicio.

## Diagrama de arquitectura

Flujo general: recibir pregunta → construir petición → consultar Gemini → extraer respuesta y calcular costo → presentar resultados.

![Diagrama de arquitectura](docs/diagrama_arquitectura.png)

## Comparación de candidatos

Pregunta utilizada:

“¿Qué etapas del ciclo de vida se evalúan al medir la huella de carbono de un producto?”

Condiciones de evaluación:

1. Cuatro solicitudes previstas por modelo, ejecutadas secuencialmente.
2. Pausa de 5 segundos entre solicitudes y parámetro de timeout de 30 segundos.
3. Medición de latencia y cálculo del costo con tokens de entrada, respuesta y razonamiento.

| Criterio | gemini-3.1-flash-lite | gemini-3.5-flash-lite | gemini-3.6-flash |
|---|---|---|---|
| Tarifa de entrada en USD por 1.000 tokens | 0,00025 | 0,00030 | 0,00075 |
| Tarifa de salida en USD por 1.000 tokens | 0,00150 | 0,00250 | 0,00375 |
| Latencias observadas en segundos | 11,92; 7,73; 29,55 | 3,64; 4,04; 6,86; 4,46 | 11,94; 10,44; 12,30; 13,00 |
| Latencia promedio en segundos | 16,40 (tres solicitudes exitosas) | 4,75 | 11,92 |
| Costo promedio por solicitud exitosa en USD | 0,001171 | 0,001936 | 0,007217 |
| Solicitudes completadas | 3 de 4 previstas | 4 de 4 | 4 de 4 |
| Calidad de la respuesta visible | No evaluable: no se imprimió | Clara y organizada; requiere revisión técnica | Detallada; requiere revisión técnica |
| Incidencias observadas | Error HTTP 503 en la cuarta solicitud | Sin errores registrados | Sin errores registrados |

Fuente de las tarifas:

- Referencia: Google AI for Developers.
- Enlace: https://ai.google.dev/gemini-api/docs/pricing
- Los valores de la tabla corresponden a las tarifas configuradas en el código.

Observaciones sobre las pruebas:

- Las prubas se realizó utilizando el código de consumir_gemini_benchmark.py, el cual es una adaptación de consumir_gemini.py.
- Los costos promedio se calcularon con los importes impresos, que están redondeados.
- Las tarifas de la tabla conservan la precisión del código; la consola las muestra con solo cuatro decimales.
- La latencia excluye las pausas entre solicitudes y los intentos fallidos.
- Solo se muestra la última respuesta de los modelos que completaron la evaluación. El código no califica automáticamente su calidad.
- La muestra permite una elección preliminar, pero no demuestra calidad consistente ni disponibilidad general.

## Justificación

Elegí provisionalmente `gemini-3.5-flash-lite` porque completó las cuatro solicitudes y obtuvo una latencia promedio de 4,75 segundos, cumpliendo el requisito definido. Una de las solicitudes superó los 5 segundos.

Su costo promedio observado fue de 0,001936 USD por consulta, aproximadamente un 73 % menor que el de `gemini-3.6-flash`. No fue el modelo más económico: `gemini-3.1-flash-lite` presentó un costo promedio menor en las solicitudes exitosas.

El criterio más relevante fue el equilibrio entre rapidez, costo y claridad.

La principal limitación es la precisión técnica. La respuesta seleccionada contiene afirmaciones que deben revisarse, como la ausencia de emisiones durante el uso de ciertos productos y el ejemplo de descomposición de una lata de aluminio.

## Alternativas descartadas y por qué

Descarté provisionalmente `gemini-3.1-flash-lite` por su mayor latencia observada y la interrupción por un error 503, aunque obtuvo el menor costo promedio. Este error aislado no permite concluir que el modelo sea menos confiable en general.

Descarté `gemini-3.6-flash` por su mayor latencia y costo. Su respuesta más detallada no demuestra una mejora suficiente para esta aplicación y también incluye afirmaciones que requieren revisión, especialmente sobre créditos ambientales y exigencias del alcance de evaluación.

## Resultados de la comparación
![Salida del código](docs/decision_arquitectura_salida.txt)
