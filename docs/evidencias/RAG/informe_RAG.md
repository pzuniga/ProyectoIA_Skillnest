# Evidencia del proyecto RAG (Skillnest, Bloque 28)

**Actividad Core:** Registra la latencia y el costo de tu flujo RAG
**Fecha de elaboración:** 20 de noviembre de 2026
**Proyecto local:** `C:\ProyectoIA_Skillnest`
**Corpus de trabajo:** NCh-ISO 14067:2019 (uso sujeto a la licencia del documento)
**Estado:** ejecución técnica de las consultas completada; publicación y revisión final de Git pendientes.

## 1. Objetivo

Instrumentar el flujo RAG de recuperación y generación para registrar latencia por etapa, consumo real de tokens y costo estimado de generación, con consultas reales y una comparación de la misma pregunta para `k=3` y `k=6`.

La implementación adapta los scripts vistos en el curso, manteniendo LangChain, Gemini Embeddings y Chroma, y distingue el código del proyecto mediante el sufijo `_proyecto`.

## 2. Configuración utilizada

| Parámetro | Valor |
|---|---|
| Documento fuente | `docs/Biblioteca/NCh-ISO 14067_2019.pdf` |
| Corpus estructurado local | `data/corpus/nch_iso_14067_2019.json` |
| Unidades de contenido | 141 documentos (131 textuales; 10 representaciones de tablas y figuras) |
| Fragmentos indexados | 318 chunks, todos con ID único |
| Chunking | `RecursiveCharacterTextSplitter`, `chunk_size=600`, `chunk_overlap=90`; unidades visuales conservadas completas |
| Embeddings | `models/gemini-embedding-001` |
| Vectorstore | `vectorstore_iso14067_cs600_ov90` (Chroma persistente) |
| Generación | `gemini-3.5-flash-lite` (configuración del script del proyecto) |
| Valores de `k` | 3 y 6 |
| Instrumentación | `embed_y_busqueda`, `armado_prompt`, `generacion` (milisegundos) |
| Tokens | `usage_metadata` devuelto por el modelo |
| Tarifas para estimación | USD 0,30 por millón de tokens de entrada y USD 2,50 por millón de tokens de salida (valores configurados en el código) |

**Identidad del corpus:** `corpus_sha256 = 4cbbb3b73be9746d50038b31d416fd022abd34c40d8d4ee6a7b8ea2ba981843e`
**Identidad del PDF:** `pdf_sha256 = d4794f4ede7d8f08aef386bc2ff99d663cbd890a3013698ae576c355ebf14f1e`

La base vectorial y los documentos normativos permanecen fuera de la carpeta de evidencias compartibles.

## 3. Ejecución de consultas reales

Los valores siguientes provienen de las salidas de PowerShell de la ejecución compartida durante el desarrollo. El archivo JSONL local es la evidencia primaria de fechas y registros individuales.

| N.º | Consulta | k | Recuperación (ms) | Prompt (ms) | Generación (ms) | Total (ms) | Tokens entrada | Tokens salida | Tokens totales | Costo estimado USD |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Condiciones para usar datos secundarios en un estudio HCP | 3 | 961,47 | 0,03 | 1.446,56 | 2.408,07 | 578 | 77 | 655 | 0,0003659 |
| 2 | Procedimiento de asignación entre coproductos | 3 | 345,18 | 0,05 | 2.071,43 | 2.416,66 | 517 | 206 | 723 | 0,0006701 |
| 3 | Factores de emisión específicos de proveedores de electricidad | 3 | 346,92 | 0,05 | 1.253,51 | 1.600,48 | 575 | 138 | 713 | 0,0005175 |
| 4 | Condiciones para usar datos secundarios en un estudio HCP (repetición) | 6 | 318,92 | 0,03 | 996,68 | 1.315,64 | 1.024 | 72 | 1.096 | 0,0004872 |
| **Total** | **4 ejecuciones** | | **1.972,49** | **0,16** | **5.768,18** | **7.740,85** | **2.694** | **493** | **3.187** | **0,0020407** |

*La suma de tiempos de etapas puede diferir en centésimas del total por redondeo de cada registro.*

### Comparación controlada de la misma pregunta

| Métrica | `k=3` | `k=6` | Diferencia observada |
|---|---:|---:|---:|
| Fragmentos solicitados | 3 | 6 | +3 |
| Tokens de entrada | 578 | 1.024 | +446 (+77,2 %) |
| Tokens de salida | 77 | 72 | -5 |
| Latencia total | 2.408,07 ms | 1.315,64 ms | -1.092,43 ms en estas dos corridas |
| Costo de generación estimado | USD 0,0003659 | USD 0,0004872 | +USD 0,0001213 (+33,2 %) |

**Interpretación:** aumentar `k` amplió el contexto de entrada y el costo estimado, pero no mejoró la respuesta sobre condiciones de uso de datos secundarios. La menor latencia observada con `k=6` no prueba una mejora de rendimiento: es una comparación de una sola corrida por configuración, sin repetición ni control del calentamiento de la conexión.

## 4. Calidad de las respuestas: limitaciones observadas

| Tema | Hallazgo del experimento | Implicación |
|---|---|---|
| Datos secundarios | El modelo identificó la obligación de justificar y documentar los datos, pero declaró no disponer de contexto suficiente para explicar todas las condiciones de utilización. | El top-k no recuperó todos los fragmentos pertinentes del apartado 6.3.5. |
| Asignación entre coproductos | La respuesta recogió criterios de asignación y el paso 3, pero omitió partes de los pasos 1 y 2. | La pertenencia al apartado 6.4.6.2 no garantiza cobertura completa del procedimiento. |
| Electricidad | La respuesta se centró en los factores de un proveedor conectado directamente; no desarrolló todas las condiciones aplicables a la electricidad de red. | Conviene evaluar la cobertura conjunta de los apartados 6.4.9.4.3 y 6.4.9.4.4. |

Estas observaciones no son mediciones de precisión/recall. Para calcular métricas de recuperación se requiere un conjunto de referencias relevantes definido y validado por pregunta. No se declara conformidad normativa a partir de las respuestas generadas.

## 5. Evaluación del cumplimiento de la actividad Core

| Criterio | Evidencia | Estado |
|---|---|---|
| Flujo RAG con recuperación y generación reales | Ejecución `src.registro_rag_proyecto` | Ejecutado |
| Tres preguntas diferentes | Consultas 1, 2 y 3 | Ejecutado |
| Comparación de una pregunta con `k=3` y `k=6` | Consultas 1 y 4 | Ejecutado |
| Latencia por etapa | `tiempos_ms` en JSONL | Ejecutado |
| Tokens reales | `usage_metadata` almacenado en `tokens` | Ejecutado |
| Costo estimado | `costo_estimado_usd` | Ejecutado |
| Registro persistente JSONL | `registros_latencia_costo.jsonl` | Generado en equipo local, según PowerShell |
| Pruebas automatizadas | 9/9 pruebas de `test_registro_rag_proyecto.py` | Superadas |
| Revisión y registro en Git | `git status`, verificación de exclusiones y commit | **Pendiente** |

## 6. Alcance de la medición de costos

Los tokens proceden de las llamadas reales registradas en `usage_metadata`. Los importes monetarios son **estimaciones calculadas con las tarifas configuradas** para generación; no constituyen prueba de facturación efectiva. La estimación no incluye el costo de los embeddings de las preguntas, los embeddings iniciales de indexación, costos de almacenamiento ni posibles efectos de caché o cambios de tarifa.

## 7. Reproducibilidad y comandos

Desde la raíz `C:\ProyectoIA_Skillnest`, en el entorno virtual:

```powershell
# Comprobar indexación persistente sin llamadas nuevas a Gemini
python -m src.indexar_norma_proyecto --estado

# Ejecutar pruebas unitarias, sin consumo de API
python -m unittest discover -s tests -p "test_registro_rag_proyecto.py" -v

# Leer evidencia ya generada, sin repetir consultas
python -m src.leer_registros_proyecto --archivo docs\evidencias\RAG\registros_latencia_costo.jsonl

# Solo si se necesitan nuevas mediciones y existe autorización para API
# python -m src.registro_rag_proyecto --actividad-core --permiso-api
```

El último comando **anexa** cuatro nuevas líneas al archivo JSONL que configure su `--salida`. No es necesario repetirlo para cerrar la entrega actual.

## 8. Inventario de evidencia y precauciones de publicación

Archivos previstos dentro de `docs/evidencias/RAG/`:

- `informe_RAG.md` (este informe, sin transcripción de la norma).
- `registros_latencia_costo.jsonl` (evidencia primaria, cuatro líneas para esta ejecución si no hay corridas anteriores).
- `recuperacion_iso14067_proyecto.json` (opcional; verificar qué comparación contiene, ya que el programa puede sobrescribirlo).

**Antes de subir a Git:** revisar que el JSONL no incluya respuestas completas, fragmentos normativos, tokens de acceso, claves API ni datos personales. Mantener fuera del repositorio los archivos `docs/Biblioteca/`, `data/corpus/`, el directorio `vectorstore_iso14067_cs600_ov90/` y `.env`. El archivo JSONL puede incluir las preguntas y metadatos de los fragmentos, por lo que debe revisarse antes de su publicación.

## 9. Conclusión y trabajo posterior

La ejecución técnica exigida por la actividad Core quedó demostrada: 4 consultas reales, comparación `k=3` y `k=6`, mediciones por etapa, tokens de uso y registro persistente. El costo estimado total de generación fue **USD 0,0020407** para **3.187 tokens** procesados por el modelo generativo.

La principal limitación detectada es la **cobertura incompleta de requisitos normativos en la recuperación top-k**, incluso cuando se recuperan fragmentos del apartado correcto. Se propone conservar esta ejecución como línea base y evaluar, en una iteración posterior, la expansión de contexto por apartado normativo. Esta mejora requerirá nuevas mediciones antes de afirmar que aumenta la calidad.
