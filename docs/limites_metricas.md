# Límites de la métrica de evaluación

## Qué mide

F1 compara los tokens de una respuesta con los de una referencia y combina precisión y cobertura según sus coincidencias, considerando sus frecuencias e ignorando su orden y significado.

La precisión indica qué proporción de los tokens de la respuesta coincide con la referencia. La cobertura indica qué proporción de los tokens de la referencia aparece en la respuesta. F1 combina ambas mediante su media armónica.

En las 20 respuestas evaluadas, los promedios fueron:

| Métrica | Promedio |
|---|---:|
| Precisión | 0,317 |
| Cobertura | 0,324 |
| F1 | 0,318 |

Estos resultados expresan similitud léxica con las referencias utilizadas. Un F1 de 0,318 no significa que el 31,8 % de las respuestas sea correcto.

## Modos de falla conocidos

- **Penalización de diferencias de vocabulario:** HCP11 obtuvo F1 de 0,154, aunque identifica consumo eléctrico, unidad y período mediante expresiones como “kilovatios-hora consumidos”. También omite instalación o proceso, fuente documental y relación con el producto. El resultado combina diferencias de redacción y omisiones, sin distinguir cuánto corresponde a cada causa.

- **Contenido válido con puntuación baja:** HCP18 obtuvo F1 de 0,150 y ofrece una justificación pertinente sobre evitar distorsiones en el cálculo. Sin embargo, no explica directamente cómo relacionar consumos y producción de períodos distintos afecta el resultado por unidad de producto. La respuesta es parcialmente útil; su puntuación no permite concluir que sea falsa.

- **Puntuación relativamente alta con información incompleta:** HCP09 obtuvo F1 de 0,526 y comunica correctamente la relación básica entre actividad y emisiones. No menciona las condiciones y unidades del coeficiente. F1 reconoce la coincidencia de términos, pero no determina si lo omitido es esencial para una definición breve o para una aplicación práctica.

- **Generalizaciones que requieren interpretación técnica:** HCP01 obtuvo F1 de 0,462. Reconoce las emisiones asociadas al producto, pero omite remociones y CO₂ equivalente, y presenta todo el ciclo de vida como alcance universal. La métrica no distingue una definición introductoria de una formulación suficientemente precisa para orientar un estudio.

- **Problemas metodológicos que el número no diagnostica:** HCP17 obtuvo el menor F1 (0,091). Propone datos históricos y literatura para estimar, pero también menciona factores de emisión promedio sin explicar cómo resolverían la ausencia de un dato de actividad. Además, omite documentar método, supuestos y limitaciones. La puntuación permite priorizar el caso, pero la revisión técnica identifica el problema.

- **Recomendaciones categóricas sin justificación:** HCP16 obtuvo F1 de 0,162. Rechaza atribuir todo el consumo a un producto, pero prescribe directamente una distribución proporcional mediante criterios físicos. No analiza primero consumos específicos y compartidos ni justifica el criterio. F1 no evalúa si una recomendación está suficientemente fundamentada.

- **Dependencia de la referencia y de la pregunta:** HCP10 obtuvo el mayor F1 (0,600). Responde correctamente que se multiplica el dato de actividad por el factor y no explicita todas las comprobaciones de la referencia. Sin embargo, la pregunta ya presupone un factor compatible. Exigir todos los elementos de la referencia sin atender a la pregunta puede sobreestimar la falta de completitud.

- **Sensibilidad al contexto:** HCP06 obtuvo F1 de 0,533 y describe la salida de fábrica como puerta del sistema. La explicación es válida en un contexto de fabricación, pero la referencia plantea una puerta definida para el estudio. La valoración requiere reconocer ese contexto; la coincidencia léxica no lo resuelve.

- **Ausencia de evaluación semántica de contradicciones:** no se identificaron contradicciones explícitas en los diez casos revisados. Esto no demuestra que F1 pueda detectarlas: el cálculo no analiza negaciones ni relaciones entre afirmaciones. Las omisiones observadas se evaluaron como falta de completitud, sin convertirlas automáticamente en contradicciones.

- **Cumplimiento formal sin garantía de calidad:** las 20 respuestas respetaron el máximo de 30 palabras, pero se observaron omisiones y simplificaciones. La extensión debe evaluarse por separado. No puede afirmarse que el límite haya causado esos problemas, porque no se compararon de forma controlada respuestas con distintas extensiones.

## Muestra revisada

Se revisaron diez de las 20 respuestas generadas mediante `consultar_modelo` y evaluadas mediante `calcular_metricas`. Se seleccionaron las cinco con menor F1 y las cinco con mayor F1.

La revisión consideró corrección factual, completitud respecto de la referencia y presencia de contradicciones explícitas.

| Caso | F1 | Corrección factual | Hallazgo principal |
|---|---:|---|---|
| HCP17 | 0,091 | Parcialmente correcta | No distingue adecuadamente cómo resolver la falta de un dato de actividad y omite documentar la estimación. |
| HCP13 | 0,108 | Parcialmente correcta | Incluye tipo y cantidad de material, pero exige “peso exacto” y omite período, proveedores y vinculación productiva. |
| HCP18 | 0,150 | Correcta | Ofrece una explicación general válida, sin desarrollar el efecto del desfase temporal por unidad de producto. |
| HCP11 | 0,154 | Correcta | Identifica consumo, unidad y período; faltan registros que permitan vincular y rastrear el dato. |
| HCP16 | 0,162 | Parcialmente correcta | Prescribe asignación proporcional sin análisis previo ni justificación del criterio. |
| HCP01 | 0,462 | Parcialmente correcta | Omite remociones y CO₂ equivalente y generaliza el alcance a todo el ciclo de vida. |
| HCP02 | 0,483 | Parcialmente correcta | Desplaza el propósito y uso previsto hacia alcance y metodología. |
| HCP09 | 0,526 | Correcta | Presenta una definición básica válida, sin condiciones ni unidades de aplicación. |
| HCP06 | 0,533 | Correcta en fabricación | Presupone la salida de fábrica sin explicitar la puerta y los procesos incluidos. |
| HCP10 | 0,600 | Correcta | Expresa el cálculo básico; las omisiones deben interpretarse considerando la compatibilidad ya supuesta en la pregunta. |

Los diez casos recibieron una valoración de completitud parcial respecto de sus referencias. No se identificaron contradicciones explícitas.

El contraste muestra que el grupo de mayor F1 contiene definiciones válidas, pero también simplificaciones relevantes. El grupo de menor F1 reúne tanto respuestas con contenido correcto como recomendaciones que requieren corrección metodológica. Por tanto, el ordenamiento no equivale a una clasificación directa de calidad técnica.

La valoración de completitud también revela una limitación del diseño del ensayo: algunas referencias reúnen varios elementos, mientras que las preguntas solicitan explicaciones breves. Deben distinguirse contenidos esenciales y aclaraciones deseables para evitar penalizar cualquier omisión con la misma severidad.

La muestra tiene las siguientes restricciones:

- La selección por extremos no es aleatoria y no permite estimar la frecuencia general de errores.
- Solo se generó una respuesta por pregunta; no se evaluó variabilidad.
- Las consultas son breves y conceptuales; no representan cálculos de inventario ni conversaciones completas.
- Las referencias propuestas requieren validación técnica y no constituyen por sí mismas evidencia normativa.
- Los resultados dependen de `procesar_texto`; no se atribuyen diferencias a operaciones específicas de limpieza que no se comprobaron en esta revisión.

## Recomendación de uso

Se puede utilizar F1 por sí solo para describir coincidencia léxica dentro de un experimento con referencias y procesamiento definidos. También sirve para ordenar casos y seleccionar respuestas para inspección.

No debe utilizarse por sí solo para aprobar respuestas del copiloto, validar decisiones metodológicas ni determinar que una orientación es técnicamente segura. Tampoco corresponde interpretar su valor como porcentaje de exactitud.

La revisión manual debe:

- Evaluar lo que la respuesta afirma, además de lo que omite.
- Distinguir errores factuales, falta de completitud y contradicciones.
- Considerar la pregunta y la necesidad del usuario, sin exigir mecánicamente toda la referencia.
- Revisar tanto puntuaciones bajas como altas.
- Priorizar recomendaciones sobre asignación, límites del sistema y tratamiento de datos faltantes.

Para mejorar el siguiente ensayo, conviene definir por pregunta los elementos esenciales esperados, validar las referencias y registrar modelo, instrucciones y versión del procesamiento. También se deben ampliar las consultas y repetir algunas ejecuciones.

No se establece un umbral de F1 para aceptación automática: los resultados disponibles no permiten justificarlo. La decisión de uso debe apoyarse en la corrección técnica y en si la respuesta permite al usuario avanzar sin introducir errores en su estudio HCP.