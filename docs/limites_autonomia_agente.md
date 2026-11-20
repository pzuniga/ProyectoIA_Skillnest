# Límites de autonomía: Copiloto HCP

- **Proyecto:** Copiloto de Huella de Carbono de Producto (HCP)
- **Unidad:** U2.4 (Actividad Core, Bloque 23)
- **Código:** `src/agente_proyecto_copiloto_hcp.py`
- **Fecha de verificación:** 19 de noviembre de 2026

## Herramientas y nivel de riesgo

El agente utiliza tres herramientas personalizadas, definidas mediante el decorador `@tool` de LangChain.

| Herramienta | Riesgo | Justificación |
|---|---|---|
| `consultar_guia_hcp` | Bajo | Consulta información de una guía interna sin modificar datos. |
| `calcular_emisiones_electricidad` | Bajo | Calcula emisiones parciales y conserva los resultados provisionales en memoria. No ejecuta escritura persistente. |
| `guardar_calculo_hcp` | Medio | Guarda resultados en un archivo JSONL. Modifica información persistente sin realizar operaciones económicas y no dispone de reversión automática. |

La clasificación considera las consecuencias de cada operación y permite establecer controles diferenciados según el riesgo.

## Herramientas que requieren aprobación humana

La herramienta `guardar_calculo_hcp` requiere aprobación humana antes de almacenar un cálculo.

Esta herramienta invoca la función `esperar_aprobacion()`, que presenta los datos del cálculo y solicita una respuesta mediante la terminal.

El mecanismo utiliza `threading` y `queue` para establecer un tiempo límite configurable (60 segundos por defecto).

Las decisiones posibles son:

- **Respuesta `s`:** autoriza el guardado.
- **Respuesta `n`:** rechaza el guardado.
- **Tiempo agotado:** rechaza automáticamente el guardado.

La decisión se registra en `docs/aprobaciones_hcp.jsonl`. Solo los cálculos aprobados pueden incorporarse a `docs/registros_hcp.jsonl`.

Las herramientas de consulta y cálculo no requieren aprobación porque no modifican registros persistentes.

**Verificación:** se comprobaron mediante ejecuciones reales la aprobación afirmativa, el rechazo explícito y el rechazo automático por tiempo agotado. En los casos rechazados no se generaron registros confirmados.

## Revisión de trazas

**Archivo principal:** `docs/trazas_hcp.jsonl`.

El agente registra las consultas recibidas, herramientas ejecutadas, argumentos, observaciones y respuestas finales. También conserva información de errores de ejecución.

**Frecuencia de revisión:**

- Después de ejecutar las pruebas automatizadas.
- Después de modificar herramientas, validaciones o instrucciones del agente.
- Antes de realizar una entrega del proyecto.

**Qué se revisa:**

- Selección incorrecta de herramientas.
- Argumentos inválidos o inesperados.
- Llamadas repetidas o innecesarias.
- Errores de ejecución y agotamiento de cuota de la API.
- Diferencias entre los resultados de las herramientas y las respuestas de Gemini.
- Intentos de guardar cálculos sin aprobación.
- Duplicación de registros persistentes.

**Evidencias de funcionamiento:**

Se ejecutaron 8 pruebas automatizadas, todas satisfactorias.

Se comprobaron ejecuciones reales con Gemini, incluyendo:

- Cálculo de emisiones y recuperación del contexto conversacional.
- Rechazo de consumos y factores negativos mediante Pydantic.
- Solicitud de información cuando falta el factor de emisión.
- Aprobación humana y guardado de un cálculo de 750 kgCO₂e.
- Rechazo explícito de un guardado de 300 kgCO₂e.
- Rechazo por timeout de 5 segundos de un guardado de 600 kgCO₂e.
- Prevención de un guardado duplicado.
- Registro de errores `GoogleRateLimitError` y `ValidationError`.

Las decisiones de aprobación se contrastaron con los registros persistentes para verificar que los cálculos rechazados no fueran guardados.

## Qué hacer ante un comportamiento inesperado

1. **Detener la operación:** interrumpir el agente o desactivar temporalmente la herramienta afectada, especialmente si realiza escrituras.
2. **Revisar las trazas:** identificar la consulta, los argumentos, la herramienta ejecutada y los mensajes de error en los registros JSONL.
3. **Corregir la causa:** ajustar las instrucciones del agente, las descripciones de herramientas, los esquemas Pydantic o las funciones Python.
4. **Verificar la corrección:** repetir las pruebas automatizadas y el escenario que produjo el error antes de continuar utilizando la herramienta.

**Limitaciones:** el Copiloto HCP es un prototipo educativo. No verifica factores de emisión oficiales, no calcula una huella de carbono de producto completa y conserva el historial conversacional y los cálculos provisionales en memoria. La versión simplificada utiliza una sesión activa por proceso y no implementa controles completos de concurrencia o autenticación multiusuario.