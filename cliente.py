import time
import random
from typing import Callable, Any
from src.consumir_gemini import armar_peticion, extraer_texto, enviar_peticion

#Esta función puede invocar a otras funciones y ejecutarlas con reintento deespués de una cantidad de segundos
#Los parámetros son: Una función, intentos, espera_segundos. Valor de retorno: cualq1uier cosa (lo que sea)
#Backoff es el tiempo de espera que se deja entre un intento fallido y el siguiente.
#Sirve para evitar repetir peticiones inmediatamente cuando un servicio está saturado o presenta un problema temporal.
#Las anotaciones de tipo (type hints) indican qué tipo de dato se espera en una variable, en los parámetros de una función o en su resultado.
#Ayudan a entender el código y a detectar posibles errores con el editor.
#Jitter es una variación aleatoria que se añade al tiempo de espera entre reintentos.
#Evita que muchos clientes vuelvan a enviar sus peticiones al mismo tiempo después de un fallo.


MODELO = "gemini-3.5-flash-lite"

def con_reintento(
    funcion: Callable[[], Any],
    intentos: int = 3,
    espera_base: float = 2,
    espera_maxima: float = 30,
) -> Any:
    for intento in range(1, intentos+1):
        try:
            return funcion()
        except TimeoutError:
            if intento == intentos:
                raise
            espera = min(espera_base * (2 ** (intento - 1)), espera_maxima)
            espera_con_jitter = espera + random.uniform(0, espera * 0.1)
            print(f"Intento {intento} de {intentos} falló por límite de uso/servidor. Reintentando en {espera_con_jitter:.1f}s..")
            time.sleep(espera_con_jitter)
 
COSTO_POR_1000_TOKENS = 0.002  # referencial, ajusta según el modelo que uses
costo_total_sesion = 0.0
 
 
def registrar_costo(respuesta: dict) -> float:
    global costo_total_sesion
    uso = respuesta.get("usageMetadata", {})
    total_tokens = uso.get("totalTokenCount", 0)
    costo_estimado = (total_tokens / 1000) * COSTO_POR_1000_TOKENS
    costo_total_sesion += costo_estimado
    print(f"Operación: {total_tokens} tokens, costo estimado: ${costo_estimado:.5f} (acumulado: ${costo_total_sesion:.5f})")
    return costo_estimado
 
 
def consultar_modelo(pregunta: str, system_instruction: str = "") -> str:
    url, cuerpo = armar_peticion(MODELO, pregunta, system_instruction, None)
    try:
         respuesta = con_reintento(lambda: enviar_peticion(url, cuerpo))
    except TimeoutError:
         raise RuntimeError("El servicio no respondió tras varios intentos. Intenta más tarde.")
    registrar_costo(respuesta)
    return extraer_texto(respuesta)
 
if __name__ == "__main__":
    resultado = consultar_modelo("¿Cuál es la capital de Chile?", "")
    print(resultado)

    for i in range(10):
        try:
            respuesta = consultar_modelo(f"Pregunta de prueba número {i}")
            print(f"Respuesta {i}: {respuesta[:60]}...")
        except RuntimeError as error:
            print(f"Respuesta {i} falló definitivamente: {error}")
    print(f"Costo total del ensayo: ${costo_total_sesion:.5f}")