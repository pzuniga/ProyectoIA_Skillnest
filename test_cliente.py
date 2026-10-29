# Mock crea objetos simulados.
# patch reemplaza temporalmente funciones o atributos durante una prueba.
from unittest.mock import patch, Mock

# pytest ejecuta las pruebas y permite comprobar excepciones.
import pytest

# Importamos directamente la función que envía peticiones.
from src.consumir_gemini import enviar_peticion

# Importamos el módulo para acceder a sus funciones y variables:
# cliente.con_reintento(), cliente.registrar_costo(), etc.
import cliente


# PRUEBAS DE ENVÍO DE PETICIONES

def test_enviar_peticion_credencial_invalida():
    # Simulamos una respuesta HTTP 401 (credencial inválida).
    respuesta_falsa = Mock(status_code=401)

    # Reemplazamos requests.post donde lo utiliza enviar_peticion.
    # En lugar de enviar una petición real, devolverá respuesta_falsa.
    with patch(
        "src.consumir_gemini.requests.post",
        return_value=respuesta_falsa,
    ):
        # La prueba pasa si enviar_peticion lanza ValueError.
        # Si no lanza ninguna excepción o lanza otra, la prueba falla.
        with pytest.raises(ValueError):
            enviar_peticion(
                "https://ejemplo.invalid",
                {"pregunta": "test"},
            )


def test_enviar_peticion_limite_de_uso():
    # Simulamos HTTP 429 (límite de uso excedido).
    # headers={} indica que no se recibió el encabezado Retry-After.
    respuesta_falsa = Mock(status_code=429, headers={})

    # Evitamos la petición HTTP real y devolvemos la respuesta simulada.
    with patch(
        "src.consumir_gemini.requests.post",
        return_value=respuesta_falsa,
    ):
        # Comprobamos que la función comunique el límite mediante TimeoutError.
        with pytest.raises(TimeoutError):
            enviar_peticion(
                "https://ejemplo.invalid",
                {"pregunta": "test"},
            )


def test_enviar_peticion_exito():
    # Simulamos HTTP 200 (petición exitosa).
    respuesta_falsa = Mock(status_code=200)

    # Definimos lo que devolverá respuesta_falsa.json() cuando se llame.
    respuesta_falsa.json.return_value = {"texto": "respuesta simulada"}

    with patch(
        "src.consumir_gemini.requests.post",
        return_value=respuesta_falsa,
    ):
        # Ejecutamos la función real usando la respuesta HTTP simulada.
        resultado = enviar_peticion(
            "https://ejemplo.invalid",
            {"pregunta": "test"},
        )

    # Verificamos que la función devuelva el diccionario esperado.
    assert resultado == {"texto": "respuesta simulada"}


# PRUEBAS DE REINTENTOS

def test_con_reintento_agota_intentos():
    # Esta operación falla cada vez que se ejecuta.
    def siempre_falla():
        raise TimeoutError("simulado")

    # Reemplazamos time.sleep para que la prueba no espere realmente.
    with patch("cliente.time.sleep"):
        # Comprobamos que el TimeoutError salga de con_reintento
        # cuando todos los intentos fallan.
        with pytest.raises(TimeoutError):
            cliente.con_reintento(siempre_falla, intentos=3)

    # Esta prueba comprueba la excepción final, pero no cuenta las llamadas.
    # Por sí sola no demuestra que se hayan ejecutado exactamente 3 intentos.


def test_con_reintento_no_reintenta_value_error():
    # side_effect hace que el Mock lance ValueError cuando se lo llame.
    operacion = Mock(side_effect=ValueError("simulado"))

    # "dormir" permite inspeccionar si se llamó a la pausa simulada.
    with patch("cliente.time.sleep") as dormir:
        # ValueError debe propagarse directamente porque con_reintento
        # solo captura TimeoutError.
        with pytest.raises(ValueError):
            cliente.con_reintento(operacion)

    # La operación debe haberse ejecutado una sola vez.
    operacion.assert_called_once()

    # No debe haber pausas, porque no corresponde reintentar este error.
    dormir.assert_not_called()


# PRUEBA DEL COSTO

def test_registrar_costo_acumula():
    # Simulamos los datos de uso de una respuesta con 1.000 tokens.
    respuesta_falsa = {
        "usageMetadata": {
            "totalTokenCount": 1000,
        }
    }

    # Establecemos temporalmente el acumulador en cero.
    # Al salir del bloque, patch restaura el valor anterior.
    # Así la prueba no depende de otras pruebas ni deja cambiado el acumulador.
    with patch("cliente.costo_total_sesion", 0.0):
        costo = cliente.registrar_costo(respuesta_falsa)

        # Con 1.000 tokens, el costo debe ser igual a la tarifa por 1.000.
        assert costo == cliente.COSTO_POR_1000_TOKENS

        # Como partimos de cero, el acumulado debe coincidir con ese costo.
        assert cliente.costo_total_sesion == cliente.COSTO_POR_1000_TOKENS


# PRUEBA DE CONSULTA AL MODELO

def test_consultar_modelo_convierte_error():
    # Simulamos el error que con_reintento propaga al agotar los intentos.
    error_simulado = TimeoutError("simulado")

    # Reemplazamos con_reintento para que lance el error inmediatamente.
    # No se ejecuta su lógica ni se envía una petición HTTP.
    with patch(
        "cliente.con_reintento",
        side_effect=error_simulado,
    ):
        # Comprobamos que consultar_modelo capture TimeoutError
        # y lo convierta en RuntimeError.
        with pytest.raises(RuntimeError):
            cliente.consultar_modelo("Pregunta de prueba")
