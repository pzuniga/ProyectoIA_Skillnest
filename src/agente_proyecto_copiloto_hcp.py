"""Copiloto HCP con herramientas, memoria conversacional y supervisión humana.

Este ejemplo usa una sesión activa por proceso. Los cálculos provisionales viven
solo en memoria. Las trazas, aprobaciones y confirmaciones se almacenan en JSONL.
No calcula una huella de carbono de producto total ni verifica factores.
"""

# ============================================================================
# 1. IMPORTACIONES
# ============================================================================
# dotenv carga configuración local; Pydantic valida los argumentos estructurados.
# LangChain expone funciones Python como herramientas y administra los turnos.
# Gemini interpreta las solicitudes, pero no realiza directamente los cálculos
# ni puede omitir la aprobación de escritura implementada en Python.
import argparse
import json
import math
import os
import queue
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, ValidationError
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableLambda
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent

# ============================================================================
# 2. CONFIGURACIÓN E INICIALIZACIÓN
# ============================================================================
# Path(__file__).resolve() permite ubicar la carpeta del proyecto aunque el
# programa se ejecute desde otra ubicación de la terminal.
RAIZ = Path(__file__).resolve().parents[1]
CARPETA_DATOS = RAIZ / "docs"
load_dotenv(RAIZ / ".env")
MODELO = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Este programa de aprendizaje utiliza una sola sesión activa por proceso.
# El historial de mensajes sí se organiza por session_id. Para servir múltiples
# usuarios en paralelo se requeriría reemplazar este estado global por una
# administración de sesiones aisladas.
SESSION_ID = "estudio_poleas_001"
CALCULOS = {}     # {UUID: registro provisional}
ORDEN = []        # UUID en orden de creación
HISTORIALES = {}  # {session_id: historial de mensajes de LangChain}
TIEMPO_APROBACION = 60
APROBACION_AGOTADA = False


def fecha_utc() -> str:
    """Genera una marca de tiempo UTC comparable entre distintos registros."""
    return datetime.now(timezone.utc).isoformat()


def anexar_jsonl(ruta: Path, registro: dict) -> None:
    """Agrega un objeto JSON por línea; no implementa transacciones de BD."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    linea = json.dumps(registro, ensure_ascii=False, allow_nan=False)
    with ruta.open("a", encoding="utf-8") as archivo:
        archivo.write(linea + "\n")


def leer_jsonl(ruta: Path) -> list[dict]:
    """Lee registros previos; permite detectar identificadores ya guardados."""
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as archivo:
        return [json.loads(linea) for linea in archivo if linea.strip()]


def extraer_texto(salida) -> str:
    """Normaliza respuestas de Gemini cuando llegan como partes estructuradas."""
    if isinstance(salida, str):
        return salida
    if isinstance(salida, list):
        return "\n".join(
            parte["text"] for parte in salida
            if isinstance(parte, dict) and isinstance(parte.get("text"), str)
        )
    return str(salida)


# ============================================================================
# 3. PERSISTENCIA Y ANÁLISIS DE TRAZABILIDAD
# ============================================================================
# intermediate_steps es la secuencia observable de herramientas ejecutadas.
# Cada acción incluye el nombre de la herramienta, sus argumentos y la salida.
# Esto no representa el razonamiento interno del modelo.
def registrar_traza(session_id: str, entrada: str, resultado: dict) -> None:
    """Conserva los pasos observables de cada consulta en trazas_hcp.jsonl."""
    acciones = [
        {"herramienta": accion.tool,
         "argumentos": accion.tool_input,
         "observacion": observacion}
        for accion, observacion in resultado.get("intermediate_steps", [])
    ]
    registro = {
        "timestamp": fecha_utc(),
        "session_id": session_id,
        "entrada": entrada,
        "estado": "ok",
        "acciones": acciones,
        "respuesta_final": extraer_texto(resultado.get("output", "")),
    }
    anexar_jsonl(CARPETA_DATOS / "trazas_hcp.jsonl", registro)


def registrar_evento(tipo: str, **datos) -> None:
    """Registra un evento en el momento de producirse, incluso entre turnos."""
    anexar_jsonl(CARPETA_DATOS / "eventos_hcp.jsonl", {
        "timestamp": fecha_utc(), "session_id": SESSION_ID,
        "evento": tipo, **datos,
    })


# ============================================================================
# 4. SUPERVISIÓN HUMANA
# ============================================================================
# threading permite leer el teclado en paralelo y queue comunica la respuesta.
# queue.get(timeout=...) deniega la solicitud si vence el tiempo establecido.
# Python no puede cancelar de manera segura un input() pendiente en otro hilo.
# Por eso, después de un timeout se detiene la sesión interactiva.
def esperar_aprobacion(mensaje: str, tiempo_limite_segundos: int = 60) -> bool:
    """Acepta únicamente 's' + Enter dentro del tiempo permitido."""
    global APROBACION_AGOTADA
    if isinstance(tiempo_limite_segundos, bool) or tiempo_limite_segundos <= 0:
        raise ValueError("El tiempo de aprobación debe ser positivo.")
    if not sys.stdin.isatty() or APROBACION_AGOTADA:
        print("Aprobación no disponible; operación rechazada.")
        return False

    cola_respuestas = queue.Queue(maxsize=1)

    def pedir_entrada():
        """Solicita la decisión y la transmite al hilo principal."""
        try:
            cola_respuestas.put(input(mensaje).strip().lower())
        except (EOFError, KeyboardInterrupt, OSError):
            cola_respuestas.put("")

    threading.Thread(target=pedir_entrada, daemon=True).start()
    try:
        respuesta = cola_respuestas.get(timeout=tiempo_limite_segundos)
    except queue.Empty:
        APROBACION_AGOTADA = True
        print("Tiempo agotado: el guardado fue rechazado.")
        return False
    except KeyboardInterrupt:
        APROBACION_AGOTADA = True
        print("Aprobación interrumpida: guardado rechazado.")
        return False
    return respuesta == "s"


def registrar_aprobacion(herramienta: str, argumentos: dict, aprobado: bool) -> None:
    """Guarda la decisión humana para asociarla al cálculo y a la sesión."""
    anexar_jsonl(CARPETA_DATOS / "aprobaciones_hcp.jsonl", {
        "timestamp": fecha_utc(),
        "session_id": SESSION_ID,
        "herramienta": herramienta,
        "argumentos": argumentos,
        "calculo_id": argumentos.get("calculo_id"),
        "aprobado": aprobado,
    })


# ============================================================================
# 5. ESQUEMAS DE VALIDACIÓN
# ============================================================================
# BaseModel especifica el formato que puede enviar el modelo a cada @tool.
# Field añade límites y descripciones; field_validator comprueba reglas extra.
class ArgumentosConsultaGuia(BaseModel):
    tema: str = Field(min_length=1, description="objetivo, electricidad o periodos")

    @field_validator("tema")
    @classmethod
    def no_vacio(cls, valor):
        if not valor.strip():
            raise ValueError("El tema no puede estar vacío.")
        return valor.strip()


class ArgumentosElectricidad(BaseModel):
    consumo_kwh: float = Field(ge=0, allow_inf_nan=False, description="Consumo eléctrico en kWh.")
    factor_kgco2e_kwh: float = Field(ge=0, allow_inf_nan=False, description="Factor en kgCO2e/kWh, proporcionado por el usuario.")
    proceso: str = Field(min_length=1, description="Proceso asociado al consumo.")
    periodo: str = Field(min_length=1, description="Período que incluye un año de cuatro cifras.")

    @field_validator("consumo_kwh", "factor_kgco2e_kwh", mode="before")
    @classmethod
    def numero_sin_formato(cls, valor):
        # Evita la interpretación errónea de "1.000" como 1,0 o 1000.
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValueError("Se requiere un número, no texto con separadores.")
        return valor

    @field_validator("proceso", "periodo")
    @classmethod
    def texto_no_vacio(cls, valor):
        if not valor.strip():
            raise ValueError("El texto no puede estar vacío.")
        return valor.strip()

    @field_validator("periodo")
    @classmethod
    def periodo_con_anio(cls, valor):
        if not re.search(r"\b(?:19|20)\d{2}\b", valor):
            raise ValueError("El período debe incluir un año de cuatro cifras.")
        return valor


class ArgumentosGuardado(BaseModel):
    calculo_id: str = Field(default="ultimo", min_length=1,
                            description="UUID del cálculo o 'ultimo' para el más reciente.")


# ============================================================================
# 6. FUENTE DE DATOS
# ============================================================================
# Es un diccionario de ejemplo, no una base de datos ni una fuente normativa.
GUIA_HCP = {
    "objetivo": "Indicar propósito, uso previsto y destinatarios del estudio.",
    "electricidad": (
        "Registrar consumo en kWh, período y año, proceso, fuente documental "
        "y distinguir consumos exclusivos de los compartidos."
    ),
    "periodos": (
        "Comparar consumos y producción de períodos coherentes; justificar "
        "cualquier diferencia temporal."
    ),
}


# ============================================================================
# 7. HERRAMIENTAS PERSONALIZADAS
# ============================================================================
# @tool expone funciones Python al modelo. La descripción de cada función
# orienta a Gemini sobre cuándo utilizarla. El cuerpo realiza operaciones
# reales de Python que pueden revisarse independientemente del modelo.
@tool(args_schema=ArgumentosConsultaGuia)
def consultar_guia_hcp(tema: str) -> str:
    """Consulta orientaciones internas sobre objetivo, electricidad o períodos."""
    clave = tema.strip().lower().replace("períodos", "periodos")
    registrar_evento("consulta_guia", tema=clave, disponible=clave in GUIA_HCP)
    return GUIA_HCP.get(clave, "Tema no disponible en la guía interna.")


@tool(args_schema=ArgumentosElectricidad)
def calcular_emisiones_electricidad(
    consumo_kwh: float, factor_kgco2e_kwh: float, proceso: str, periodo: str
) -> str:
    """Calcula emisiones eléctricas parciales y conserva el resultado provisional."""
    # Se valida otra vez para no depender únicamente de la conversión de @tool.
    datos = ArgumentosElectricidad.model_validate({
        "consumo_kwh": consumo_kwh,
        "factor_kgco2e_kwh": factor_kgco2e_kwh,
        "proceso": proceso,
        "periodo": periodo,
    })
    emisiones = datos.consumo_kwh * datos.factor_kgco2e_kwh
    if not math.isfinite(emisiones):
        raise ValueError("El resultado no es un número finito.")

    calculo_id = str(uuid4())
    CALCULOS[calculo_id] = {
        "calculo_id": calculo_id,
        "session_id": SESSION_ID,
        "timestamp_calculo": fecha_utc(),
        "proceso": datos.proceso,
        "periodo": datos.periodo,
        "consumo_kwh": datos.consumo_kwh,
        "factor_kgco2e_kwh": datos.factor_kgco2e_kwh,
        "emisiones_kgco2e": emisiones,
        "factor_verificado": False,
        "alcance_resultado": "Electricidad de una actividad; no HCP total",
        "guardado": False,
    }
    ORDEN.append(calculo_id)
    registrar_evento("calculo_provisional", calculo_id=calculo_id,
                    emisiones_kgco2e=emisiones)
    return (f"Cálculo ID: {calculo_id}. Emisiones: {emisiones:,.2f} kgCO2e. "
            "Resultado provisional y parcial. Factor NO verificado.")


@tool(args_schema=ArgumentosGuardado)
def guardar_calculo_hcp(calculo_id: str = "ultimo") -> str:
    """Guarda un cálculo provisional exclusivamente tras aprobación humana."""
    clave = calculo_id.strip()
    if clave.lower() in ("ultimo", "último"):
        if not ORDEN:
            return "No existen cálculos en la sesión."
        clave = ORDEN[-1]

    registro = CALCULOS.get(clave)
    if registro is None or registro["session_id"] != SESSION_ID:
        return "No existe ese cálculo en la sesión actual."
    ruta_registros = CARPETA_DATOS / "registros_hcp.jsonl"
    repetido = any(
        previo.get("calculo_id") == clave and previo.get("session_id") == SESSION_ID
        for previo in leer_jsonl(ruta_registros)
    )
    if registro["guardado"] or repetido:
        return f"El cálculo {clave} ya fue guardado."

    # Antes de cualquier escritura del cálculo, Python pide autorización.
    mensaje = (
        "\nSOLICITUD DE APROBACIÓN PARA GUARDAR\n"
        f"ID: {clave}\nProceso: {registro['proceso']}\n"
        f"Período: {registro['periodo']}\n"
        f"Consumo: {registro['consumo_kwh']} kWh\n"
        f"Factor: {registro['factor_kgco2e_kwh']} kgCO2e/kWh (NO verificado)\n"
        f"Emisiones: {registro['emisiones_kgco2e']} kgCO2e\n"
        f"¿Aprueba el guardado? (s/n; {TIEMPO_APROBACION} s): "
    )
    aprobado = esperar_aprobacion(mensaje, TIEMPO_APROBACION)
    registrar_aprobacion("guardar_calculo_hcp", {"calculo_id": clave}, aprobado)
    registrar_evento("aprobacion", calculo_id=clave, aprobado=aprobado)
    if not aprobado:
        return "Guardado rechazado: no existe aprobación humana."

    # Solo el registro confirmado se escribe; los provisionales siguen en RAM.
    confirmado = {**registro, "guardado": True, "timestamp_guardado": fecha_utc()}
    try:
        anexar_jsonl(ruta_registros, confirmado)
    except Exception as error:
        registrar_evento("error_guardado", calculo_id=clave,
                        tipo_error=type(error).__name__)
        raise
    registro.update(confirmado)
    registrar_evento("guardado_confirmado", calculo_id=clave)
    return (f"Cálculo {clave} guardado correctamente. Guardar NO significa "
            "verificar ni certificar su metodología.")


herramientas = [consultar_guia_hcp, calcular_emisiones_electricidad, guardar_calculo_hcp]


# ============================================================================
# 8. GESTIÓN DEL HISTORIAL EN MEMORIA
# ============================================================================
# El session_id separa historiales de mensajes. La memoria no persiste
# cuando el proceso termina. No equivale al registro permanente de cálculos.
def obtener_historial(session_id: str):
    """Recupera o crea el historial de mensajes de una sesión."""
    if session_id not in HISTORIALES:
        HISTORIALES[session_id] = InMemoryChatMessageHistory()
    return HISTORIALES[session_id]


# ============================================================================
# 9. CONSTRUCCIÓN DEL AGENTE
# ============================================================================
# El prompt mantiene un lugar para el historial y otro para las acciones que
# el ejecutor necesita coordinar. intermediate_steps almacena las acciones
# observables para la auditoría; verbose=True las muestra durante el turno.
def construir_agente():
    """Configura Gemini, herramientas, ejecutor y memoria conversacional."""
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        raise RuntimeError("Falta GOOGLE_API_KEY o GEMINI_API_KEY en .env")

    modelo = ChatGoogleGenerativeAI(model=MODELO, temperature=0)
    prompt_agente = ChatPromptTemplate.from_messages([
        ("system",
         "Eres un copiloto educativo de huella de carbono de producto. "
         "Responde en español de forma clara. "
         "Consulta la guía interna solo para objetivo, electricidad o periodos. "
         "No afirmes haber consultado normas, PDF o Internet. "
         "Calcula solo emisiones parciales de electricidad con consumo, factor, "
         "proceso y período con año aportados por el usuario. "
         "No inventes datos o factores. Si faltan, pregunta. "
         "Usa chat_history para 'el mismo factor' o 'el doble de consumo'. "
         "Cuando se solicite guardar el último cálculo, invoca "
         "guardar_calculo_hcp(calculo_id='ultimo'); no recalcules. "
         # La observación devuelta por la herramienta determina
         # el estado de la operación de guardado.
         "Interpreta el resultado de guardar_calculo_hcp como "
         "el estado definitivo de esa operación. "
         # El modelo informa la decisión tomada por el sistema
         # sin solicitar una nueva autorización en el mismo turno.
         "Si la herramienta indica que el guardado fue rechazado, "
         "informa que el cálculo no fue guardado. "
         "No solicites nuevamente aprobación en esa respuesta. "
         # La herramienta también puede detectar que el cálculo
         # fue guardado en una operación anterior.
         "Si el cálculo ya estaba guardado, informa esa situación "
         "sin solicitar otra aprobación. "
         # El resultado confirmado se comunica sin atribuirle
         # una validez metodológica que no ha sido comprobada.
         "Si el guardado fue exitoso, confirma la operación. "
         "No afirmes que guardar equivale a verificar, certificar "
         "o calcular HCP total. "
         # No se atribuye un motivo específico cuando la herramienta
         # solamente informa que no existe aprobación humana.
         "No inventes la causa de un rechazo si la herramienta "
         "no la identifica explícitamente. "
         "No afirmes que guardar equivale a verificar, certificar o calcular HCP total. "
         "Los números de herramientas deben ser números JSON, no texto regional."),
        MessagesPlaceholder("chat_history"),
        ("human", "{entrada}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agente = create_tool_calling_agent(modelo, herramientas, prompt_agente)
    ejecutor_agente = AgentExecutor(
        agent=agente,
        tools=herramientas,
        verbose=True,
        return_intermediate_steps=True,
        max_iterations=6,
    )
    limpiar_salida = RunnableLambda(
        lambda datos: {**datos, "output": extraer_texto(datos.get("output", ""))}
    )
    cadena_agente = ejecutor_agente | limpiar_salida
    return RunnableWithMessageHistory(
        cadena_agente,
        obtener_historial,
        input_messages_key="entrada",
        history_messages_key="chat_history",
        output_messages_key="output",
    )


# ============================================================================
# 10. EJECUCIÓN DEL PROGRAMA
# ============================================================================

def ejecutar_turno(agente_con_memoria, entrada: str) -> None:
    """
    Ejecuta una consulta, registra su resultado y presenta
    mensajes comprensibles cuando se producen errores.
    """

    try:
        # El agente recibe la consulta y el identificador
        # de sesión utilizado para recuperar su historial.
        resultado = agente_con_memoria.invoke(
            {"entrada": entrada},
            config={"configurable": {"session_id": SESSION_ID}},
        )

    except Exception as error:

        # El error se registra antes de presentar
        # el mensaje correspondiente en consola.
        try:
            anexar_jsonl(
                CARPETA_DATOS / "trazas_hcp.jsonl",
                {
                    "timestamp": fecha_utc(),
                    "session_id": SESSION_ID,
                    "entrada": entrada,
                    "estado": "error",
                    "tipo_error": type(error).__name__,
                    "detalle": str(error),
                },
            )

        except Exception as error_traza:
            # Un fallo en el registro se informa sin ocultar
            # la excepción original del agente.
            print(
                "ALERTA: no fue posible registrar el error:",
                error_traza,
            )

        # Los errores de Pydantic reciben un tratamiento
        # específico para facilitar su comprensión.
        if isinstance(error, ValidationError):

            print("\nDATOS NO VÁLIDOS:")

            # errors() devuelve una lista estructurada
            # con los campos y las reglas incumplidas.
            for detalle in error.errors():

                campo = ".".join(
                    str(elemento)
                    for elemento in detalle["loc"]
                )

                tipo_error = detalle["type"]

                if tipo_error == "greater_than_equal":

                    minimo = detalle.get(
                        "ctx", {}
                    ).get("ge", 0)

                    print(
                        f"El campo '{campo}' debe "
                        f"ser mayor o igual a {minimo}."
                    )

                else:
                    print(
                        f"El campo '{campo}' "
                        "contiene un valor inválido."
                    )

            print(
                "\nRevisa los datos e intenta nuevamente."
            )

        else:
            # Los errores de conexión, cuota u otras
            # excepciones mantienen el mensaje original.
            print("ERROR del agente:", error)

        # La ejecución termina después de procesar el error.
        # Esto evita utilizar una variable resultado inexistente.
        return

    # Este bloque solo se ejecuta cuando la invocación
    # del agente ha finalizado sin excepciones.
    try:
        registrar_traza(SESSION_ID, entrada, resultado)

    except Exception as error:
        print(
            "ALERTA: el agente respondió, "
            "pero no se registró la traza:",
            error,
        )

    # Presenta la respuesta generada por el agente.
    print("\nRESPUESTA:\n", resultado.get("output", ""))



CONSULTAS_DEMO = [
    "¿Qué datos recopilo sobre electricidad?",
    ("Para fabricar poleas en enero de 2026 consumí 1.000 kWh; "
     "el factor ficticio es 0,2 kgCO2e/kWh. Calcula sin guardar."),
    "¿Cuánto sería con el doble de consumo y el mismo factor? No guardes.",
    "Guarda el último cálculo.",
]


def main():
    """Permite ejecutar una demostración o ingresar consultas por terminal."""
    global SESSION_ID, TIEMPO_APROBACION
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modo", choices=("demo", "interactivo"), default="interactivo")
    parser.add_argument("--sesion", default="estudio_poleas_001")
    parser.add_argument("--timeout-aprobacion", type=int, default=60)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.sesion):
        parser.error("--sesion debe tener 1-64 caracteres alfanuméricos, _ o -")
    if args.timeout_aprobacion <= 0:
        parser.error("--timeout-aprobacion debe ser mayor que cero")
    SESSION_ID = args.sesion
    TIEMPO_APROBACION = args.timeout_aprobacion

    agente_con_memoria = construir_agente()
    if args.modo == "demo":
        for entrada in CONSULTAS_DEMO:
            print("\nCONSULTA:", entrada)
            ejecutar_turno(agente_con_memoria, entrada)
            if APROBACION_AGOTADA:
                print("Demostración detenida tras vencimiento de aprobación.")
                break
        return

    print("COPILOTO HCP. Escribe salir para terminar.")
    while not APROBACION_AGOTADA:
        try:
            entrada = input("\nTu consulta: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if entrada.lower() == "salir":
            break
        if entrada:
            ejecutar_turno(agente_con_memoria, entrada)
    if APROBACION_AGOTADA:
        print("Sesión cerrada después del timeout. Reinicia para continuar.")


if __name__ == "__main__":
    main()
