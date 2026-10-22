import os
import requests
from dotenv import load_dotenv
import time

load_dotenv()

# Construcción del endpoint y payload de la consulta para Gemini, contenido real o los datos importantes que se transmiten en un mensaje
def armar_peticion(pregunta):
    api_key = os.getenv("GEMINI_API_KEY")
    modelo = "gemini-3.5-flash-lite"  # "gemini-3.5-flash-lite, gemini-3.6-flash, gemini-3.1-flash-lite
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
  

def obtener_dato_de_prueba(pregunta):
    """
    Ejecuta el flujo completo de prueba con la API de Gemini:
    construye la consulta, envía la petición HTTP midiendo su latencia,
    calcula el costo monetario según el consumo de tokens y devuelve
    la respuesta generada en texto plano.
    """
    # 1. Construir la URL del endpoint y la estructura del cuerpo (body) en JSON
    url, body = armar_peticion(pregunta)

    # 2. Medir el tiempo de respuesta (latencia) de la petición HTTP
    inicio = time.perf_counter()
    datos = enviar_peticion(url, body)
    fin = time.perf_counter()

    latencia = fin - inicio
    print(f"Latencia: {latencia:.2f} segundos")

    # 3. Calcular el costo estimado según el consumo de tokens y tarifas por token
    costo = calcular_costo(datos, 0.00000075, 0.00000375)
    print(f"Costo de la petición: {costo:.6f} USD")

    # 4. Extraer y retornar únicamente el texto de la respuesta del modelo
    return extraer_texto(datos)



def calcular_costo(datos, precio_entrada, precio_salida):
    # Extrae el bloque de consumo de tokens reportado por la API
    uso = datos["usageMetadata"]

    # Conteo de tokens según su tipo:
    tokens_entrada = uso["promptTokenCount"]                # Tokens de la consulta/prompt enviada
    tokens_salida = uso["candidatesTokenCount"]             # Tokens del texto final generado
    tokens_razonamiento = uso.get("thoughtsTokenCount", 0)  # Tokens de pensamiento interno (0 si el modelo no razona)

    # Costo total: entrada por su tarifa + salida (incluyendo razonamiento) por su tarifa
    costo = (tokens_entrada * precio_entrada) + ((tokens_salida + tokens_razonamiento) * precio_salida)

    return costo


try:
     print(obtener_dato_de_prueba("Confirma en una frase corta que esta conexión funciona"))
except (ValueError, RuntimeError) as error:
     print ("No se pudo completar la operación: ", error)