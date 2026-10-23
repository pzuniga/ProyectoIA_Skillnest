import os
import requests
from dotenv import load_dotenv
import time
import json
import re           #Librería de expresiones regulares para encontrar patrones
load_dotenv()


# Constantes (variable en mayúscula)
MODELO = "gemini-3.5-flash-lite"
URL_BASE = "https://generativelanguage.googleapis.com/v1beta/models/"
API_KEY = os.getenv("GEMINI_API_KEY")
SYSTEM_INSTRUCTION = "Eres un asistente amigable y respondes en máximo tres palabras en español, tres en francés, tres en inglés}"
RESPONSE_SCHEMA = {                          #Estructura esperada de una respuesta
     "type": "OBJECT",                        #La respuesta debe ser un objeto con campos y valores
          "properties": {                      #Define los campos esperados
          "categoria": {"type": "STRING"},     #El campo categoría debe contener texto
          "nivel": {"type": "NUMBER"}          #El campo nivel debe contener número
     },
     "required": ["categoria", "nivel"]       #Ambos campos son obligatorios
}

  
def armar_peticion(modelo, pregunta, system_instruction, response_schema=None):      #response_shema puede o no estar en la consulta
     if not pregunta:
         raise ValueError("La pregunta no puede estar vacía")
     url = f"{URL_BASE}{modelo}:generateContent?key={API_KEY}"
     body = {
         "systemInstruction": {                                  #Indicar cómo debe responder el sistema, en este caso una lista de partes del mensaje (contiene texto)
             "parts": [{"text": system_instruction}]             
         },
         "contents": [{"parts": [{"text": pregunta}]}]           #Entregar el mensaje, en este caso una pregunta del usuario (una lista con una parte de texto)

         }
     if response_schema is not None:
         body["generationConfig"] = {                            #Configurar el formato de la respuesta, formato JSON con estructura obligatoria
             "responseMimeType": "application/json",
             "responseSchema": response_schema
         }
     return url, body
  
def enviar_peticion(url, body):
     try:
        respuesta = requests.post(url, json=body, timeout=30)
     except requests.exceptions.ConnectionError:
         raise RuntimeError("No se pudo conectar con el servicio. Intenta de nuevo en unos momentos")
     except requests.exceptions.Timeout:
         raise RuntimeError("Se agotó el tiempo. Intenta de nuevo en unos momentos")
     if respuesta.status_code !=200:
         raise RuntimeError(f"Error en la petición. status Code: {respuesta.status_code}")
     try:
         return respuesta.json()
     except requests.exceptions.JSONDecodeError:
         raise RuntimeError("La respuesta del servicio no llegó en el formato esperado")
  
def extraer_texto(datos): #Gemini
     try:
         return datos["candidates"][0]["content"]["parts"][0]["text"]
     except (KeyError, IndexError):
         raise RuntimeError("La respuesta no recibe el texto generado en el lugar definido") 
  
def obtener_dato_de_prueba(pregunta):
     url, body = armar_peticion(MODELO, pregunta, SYSTEM_INSTRUCTION, RESPONSE_SCHEMA)
     inicio = time.perf_counter()       #Empezar el contador
     datos = enviar_peticion(url, body)
     fin = time.perf_counter ()         #Términa el contador
     latencia = fin - inicio
     print(f"Latencia: {latencia:.2f} segundos")       #Imprime latencia en pantalla

     costo = calcular_costo(datos, 0.00000075, 0.00000375)
     print(f"Costo de la petición: {costo:.6f} USD")
     texto = extraer_texto(datos)
     datos_formateados = parsear_respuesta_json(texto, ["categoria", "nivel"] ) 
     return datos_formateados

#def calcular el cosoto del envío y respuesta 
def calcular_costo(datos, precio_entrada, precio_salida):
     uso = datos["usageMetadata"]
     tokens_entrada = uso.get("promptTokenCount",0)
     tokens_salida = uso.get("candidatesTokenCount",0)
     tokens_razonamiento = uso.get("thoughtsTokenCount",0)
     costo = (tokens_entrada * precio_entrada) + ((tokens_salida+tokens_razonamiento)*precio_salida)
     return costo

# Función para parsear respuesta JSON
def parsear_respuesta_json (texto, claves_requeridas=None):
    texto_limpio = texto.strip()                  #Limpiar espacios vacíos al inicio y al final
    texto_limpio = re.sub(r"^```(?:json)?\s*", "", texto_limpio)           #Quitar las marca inicial de un bloque de código Marksown
    texto_limpio = re.sub(r"\s*```$", "", texto_limpio)                    ##Quitar las marca final de un bloque de código Marksown
    try:
        datos = json.loads(texto_limpio)          #Lanzar una excepción si el json no es válido
    except json.JSONDecodeError:
        raise ValueError("La respuesta del modelo noes JSON válido")
    if claves_requeridas:
        faltantes = {clave for clave in claves_requeridas if clave not in datos}     # En este caso "claves requeridas = ["categoia", "nivel"]"
        if faltantes:
            raise ValueError("La respuesta no tiene la estructura esperada")
    return datos

# Sólo ejecutar si el archivo en el que estoy se encuentra directamente ejecutado
if __name__ == "__main__":
    try:
        print(obtener_dato_de_prueba("Confirma en una frase corta que esta conexión funciona"))
    except (ValueError, RuntimeError) as error:
        print ("No se pudo completar la operación: ", error)