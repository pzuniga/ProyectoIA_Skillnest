"""Siete pruebas críticas del enrutamiento del copiloto HCP."""

import logging
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from src.enrutamiento_proyecto import (
    RESPUESTA_RESPALDO,
    RESPUESTA_ERROR,
    construir_paso_clasificacion,
    construir_flujo,
    procesar_mensaje_seguro,
)


# PRUEBA 1: NORMALIZACIÓN DE LA CLASIFICACIÓN

def test_clasificacion_normaliza_texto():
    # El modelo simulado devuelve espacios, mayúsculas y un salto.
    modelo_falso = RunnableLambda(
        lambda entrada: AIMessage(content="  RECOPILACION\n")
    )

    clasificador = construir_paso_clasificacion(modelo_falso)

    resultado = clasificador.invoke({
        "mensaje": "¿Qué datos eléctricos debo recopilar?",
    })

    # La categoría debe quedar limpia y en minúsculas.
    assert resultado == "recopilacion"


# FUNCIÓN DE APOYO PARA COMPROBAR EL FLUJO COMPLETO

def comprobar_ruta(categoria, mensaje, fragmento_esperado):
    """Comprueba que el flujo seleccione la plantilla correspondiente."""

    # La primera llamada clasifica y la segunda genera la respuesta.
    modelo_falso = MagicMock(side_effect=[
        AIMessage(content=categoria),
        AIMessage(content="Respuesta simulada de la ruta."),
    ])

    cadena = construir_flujo(
        RunnableLambda(modelo_falso)
    )

    resultado = procesar_mensaje_seguro(cadena, mensaje)

    assert resultado == "Respuesta simulada de la ruta."
    assert modelo_falso.call_count == 2

    # La segunda llamada debe utilizar la plantilla de la ruta esperada.
    prompt = modelo_falso.call_args_list[1].args[0].to_string()

    assert fragmento_esperado in prompt

    # El mensaje original debe conservarse hasta la respuesta.
    assert mensaje in prompt


# PRUEBA 2: RUTA DE DEFINICIÓN

def test_flujo_enruta_definicion():
    comprobar_ruta(
        categoria="definicion",
        mensaje="¿Cómo defino el objetivo del estudio?",
        fragmento_esperado="destinatarios",
    )


# PRUEBA 3: RUTA DE RECOPILACIÓN

def test_flujo_enruta_recopilacion():
    comprobar_ruta(
        categoria="recopilacion",
        mensaje="¿Qué registros eléctricos debo recopilar?",
        fragmento_esperado="fuentes documentales",
    )


# PRUEBA 4: RUTA DE REVISIÓN

def test_flujo_enruta_revision():
    comprobar_ruta(
        categoria="revision",
        mensaje="Revisa mi consumo anual y mi producción de enero.",
        fragmento_esperado="problemas observables",
    )


# PRUEBA 5: RUTA POR DEFECTO

def test_flujo_enruta_otro():
    # Solo se necesita una respuesta del modelo para clasificar.
    modelo_falso = MagicMock(
        return_value=AIMessage(content="otro")
    )

    cadena = construir_flujo(
        RunnableLambda(modelo_falso)
    )

    resultado = procesar_mensaje_seguro(
        cadena,
        "¿Qué película puedo ver?",
    )

    assert "¿Necesitas definir el estudio" in resultado

    # La aclaración es fija: no debe existir una segunda consulta.
    assert modelo_falso.call_count == 1


# PRUEBA 6: RESPALDO ANTE FALLO DE LAS RUTAS

def test_flujo_recupera_fallos_de_las_tres_rutas(caplog):
    # Se comprueba cada ruta dentro de una sola prueba.
    for categoria in ("definicion", "recopilacion", "revision"):
        caplog.clear()

        # La clasificación funciona y la generación de respuesta falla.
        modelo_falso = MagicMock(side_effect=[
            AIMessage(content=categoria),
            ConnectionError("fallo simulado"),
        ])

        cadena = construir_flujo(
            RunnableLambda(modelo_falso)
        )

        with caplog.at_level(logging.WARNING):
            resultado = procesar_mensaje_seguro(
                cadena,
                "Consulta HCP de prueba",
            )

        # El resultado debe proceder del respaldo específico.
        assert resultado == RESPUESTA_RESPALDO, categoria
        assert modelo_falso.call_count == 2, categoria

        # El fallo debe registrarse para facilitar su diagnóstico.
        assert (
            "Falló una operación del copiloto HCP"
            in caplog.text
        ), categoria
        assert "ConnectionError" in caplog.text, categoria


# PRUEBA 7: FALLO DE CLASIFICACIÓN

def test_fallo_clasificacion_activa_proteccion_general(caplog):
    # El modelo falla en la primera llamada, antes de elegir una ruta.
    modelo_falso = MagicMock(
        side_effect=ConnectionError("clasificación fallida")
    )

    cadena = construir_flujo(
        RunnableLambda(modelo_falso)
    )

    with caplog.at_level(logging.ERROR):
        resultado = procesar_mensaje_seguro(
            cadena,
            "¿Qué datos debo recopilar?",
        )

    # La excepción debe ser manejada por el try/except general.
    assert resultado == RESPUESTA_ERROR

    # No debe intentarse generar una respuesta de destino.
    assert modelo_falso.call_count == 1

    # El fallo debe quedar registrado.
    assert "No se pudo procesar la consulta" in caplog.text
    assert "ConnectionError" in caplog.text