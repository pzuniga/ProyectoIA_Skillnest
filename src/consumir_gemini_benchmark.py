import os
import requests
from dotenv import load_dotenv
import time
from datetime import datetime

load_dotenv()

# Construcción del endpoint y payload de la consulta para Gemini
def armar_peticion(pregunta, modelo):
    api_key = os.getenv("GEMINI_API_KEY")
    if not pregunta:
        raise ValueError("La pregunta no puede estar vacía")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": pregunta}]}]}
    return url, body

# Envío de la petición HTTP y control de errores del servicio
def enviar_peticion(url, body):
    try:
        respuesta = requests.post(url, json=body, timeout=30)
    except requests.exceptions.ConnectionError:
        raise RuntimeError("No se pudo conectar con el servicio. Intenta de nuevo en unos momentos")
    except requests.exceptions.Timeout:
        raise RuntimeError("Se agotó el tiempo. Intenta de nuevo en unos momentos")
    if respuesta.status_code != 200:
        raise RuntimeError(f"Error en la petición. status Code: {respuesta.status_code}")
    try:
        return respuesta.json()
    except requests.exceptions.JSONDecodeError:
        raise RuntimeError("La respuesta del servicio no llegó en el formato esperado")

# Extracción de la respuesta en texto generada por Gemini
def extraer_texto(datos):
    try:
        return datos["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise RuntimeError("La respuesta no recibe el texto generado en el lugar definido")

# Cálculo del costo por petición según el consumo de tokens
def calcular_costo(datos, precio_entrada, precio_salida):
    uso = datos.get("usageMetadata", {})
    tokens_entrada = uso.get("promptTokenCount", 0)
    tokens_salida = uso.get("candidatesTokenCount", 0)
    tokens_razonamiento = uso.get("thoughtsTokenCount", 0)

    costo = (tokens_entrada * precio_entrada) + ((tokens_salida + tokens_razonamiento) * precio_salida)
    return costo

# Medición del rendimiento sobre múltiples repeticiones y presentación de la tabla
def evaluar_rendimiento(pregunta, modelo, precio_entrada, precio_salida, repeticiones=4):
    latencias = []
    respuesta_json = None
    fecha_hora_prueba = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"\n========================================================")
    print(f"Evaluando: {modelo} | Inicio: {fecha_hora_prueba}")
    print(f"========================================================")

    for i in range(repeticiones):
        url, body = armar_peticion(pregunta, modelo)
        inicio = time.perf_counter()
        respuesta_json = enviar_peticion(url, body)
        fin = time.perf_counter()

        duracion = fin - inicio
        latencias.append(duracion)

        costo_intento = calcular_costo(respuesta_json, precio_entrada, precio_salida)
        texto_intento = extraer_texto(respuesta_json)

        print(f"\n--- Intento {i + 1} ---")
        print(f"Latencia: {duracion:.2f} segundos")
        print(f"Costo: {costo_intento:.6f} USD")
        
        if i < repeticiones - 1:
            time.sleep(5)

    latencia_promedio = sum(latencias) / len(latencias)
    texto_final = extraer_texto(respuesta_json)

    # Conversión del precio unitario por token a precio por cada 1.000 tokens
    costo_1000_entrada = precio_entrada * 1000
    costo_1000_salida = precio_salida * 1000

    # Imprimir la tabla comparativa de resultados
    print("\n" + "=" * 80)
    print(f"{'Criterio':<40} | {modelo:<35}")
    print("-" * 80)
    print(f"{'Fecha y hora de prueba':<40} | {fecha_hora_prueba:<35}")
    print(f"{'Costo por 1000 tokens de entrada':<40} | {costo_1000_entrada:.4f} USD")
    print(f"{'Costo por 1000 tokens de salida':<40} | {costo_1000_salida:.4f} USD")
    print(f"{'Latencia promedio observada':<40} | {latencia_promedio:.2f} segundos")
    print("=" * 80)
    print(f"Calidad de respuesta para tu caso concreto:\n{texto_final.strip()}\n")

    return texto_final, latencia_promedio


# Ejecución secuencial de los tres modelos
# Sólo ejecutar si el archivo en el que estoy se encuentra directamente ejecutado
if __name__ == "__main__":
    pregunta = (
        "¿Qué etapas del ciclo de vida se evalúan al medir "
        "la huella de carbono de un producto?"
    )

    # Todas las tarifas están expresadas en USD por 1.000 tokens
    config_modelos = {
        "gemini-3.1-flash-lite": {
            "precio_entrada": 0.00025,
            "precio_salida": 0.00150
        },
        "gemini-3.5-flash-lite": {
            "precio_entrada": 0.00030,
            "precio_salida": 0.00250
        },
        "gemini-3.6-flash": {
            "precio_entrada": 0.00075,
            "precio_salida": 0.00375
        }
    }

    for mod, tarifas in config_modelos.items():
        try:
            evaluar_rendimiento(
                pregunta=pregunta,
                modelo=mod,
                precio_entrada=tarifas["precio_entrada"] / 1000,
                precio_salida=tarifas["precio_salida"] / 1000,
                repeticiones=4
            )
        except (ValueError, RuntimeError) as error:
            print(
                f"No se pudo completar la operación para {mod}: {error}"
            )