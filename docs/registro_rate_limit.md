## Registro del ensayo de rate limit

- Fecha: 2026-10-28
- Consultas realizadas: 11 (una inicial y diez de prueba).
- Intentos de envío: 13 (11 exitosos y 2 fallidos).
- Primer fallo observado: sexta consulta del ensayo, correspondiente a “Pregunta de prueba número 4”.
- Código HTTP del fallo: no registrado. No se pudo confirmar si correspondía a un 429.
- Reintentos necesarios: 2. La consulta afectada terminó correctamente en el tercer intento.
- Esperas observadas: 2.0 s y 4.1 s, compatibles con backoff exponencial con jitter.
- Tokens registrados: 419.
- Costo estimado total: USD 0.00084, calculado con la tarifa referencial de USD 0.002 por cada 1.000 tokens.
- Resultado: las 11 consultas terminaron correctamente. Una requirió dos reintentos.
- Mejora pendiente: registrar el código HTTP y el mensaje del proveedor para identificar la causa de los fallos.