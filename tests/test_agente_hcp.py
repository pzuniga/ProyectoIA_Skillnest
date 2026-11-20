"""
Pruebas automatizadas del Copiloto HCP.

Los escenarios verifican las herramientas, las validaciones,
la aprobación humana y la trazabilidad del agente.

Las pruebas utilizan datos ficticios y simulaciones locales.
No realizan llamadas a Gemini ni requieren credenciales.
"""

import json
import tempfile
import threading
import unittest

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pydantic import ValidationError

from src import agente_proyecto_copiloto_hcp as hcp


# ============================================================
# PRUEBAS AUTOMATIZADAS DEL COPILOTO HCP
# ============================================================

class PruebasHCP(unittest.TestCase):
    """Agrupa las pruebas locales de las herramientas del agente."""

    def setUp(self):
        """Prepara un entorno independiente para cada prueba."""

        # Se crea una carpeta temporal para almacenar los archivos
        # JSONL generados durante la ejecución de cada escenario.
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)

        # Se conservan los valores originales de configuración
        # para restaurarlos al finalizar cada prueba.
        self.path_anterior = hcp.CARPETA_DATOS
        self.sesion_anterior = hcp.SESSION_ID
        self.aprobacion_anterior = hcp.APROBACION_AGOTADA

        # Se redirige el almacenamiento hacia la carpeta temporal.
        hcp.CARPETA_DATOS = Path(self.temporal.name)

        # Se eliminan los cálculos provisionales anteriores
        # para evitar interferencias entre escenarios.
        hcp.CALCULOS.clear()
        hcp.ORDEN.clear()

        # Se establece una sesión identificable para las pruebas.
        hcp.SESSION_ID = "prueba_A"
        hcp.APROBACION_AGOTADA = False

        # Se registra la restauración del estado original.
        self.addCleanup(self.restaurar)

        # Se define un conjunto de datos ficticios que será
        # reutilizado en los escenarios de cálculo y guardado.
        self.datos = {
            "consumo_kwh": 2000,
            "factor_kgco2e_kwh": 0.2,
            "proceso": "fabricación de poleas",
            "periodo": "enero de 2026",
        }

    def restaurar(self):
        """Restablece la configuración utilizada antes de la prueba."""

        # Se recuperan las rutas y variables globales originales.
        hcp.CARPETA_DATOS = self.path_anterior
        hcp.SESSION_ID = self.sesion_anterior
        hcp.APROBACION_AGOTADA = self.aprobacion_anterior

        # Se limpia la memoria provisional utilizada en las pruebas.
        hcp.CALCULOS.clear()
        hcp.ORDEN.clear()

    # ========================================================
    # 1. CONSULTA DE LA GUÍA INTERNA
    # ========================================================

    def test_consulta_guia(self):
        """Verifica la consulta de información metodológica interna."""

        # Se ejecuta directamente la función de consulta
        # asociada a la herramienta de LangChain.
        respuesta = hcp.consultar_guia_hcp.func("electricidad")

        # Se comprueba que la orientación recuperada
        # incluya la unidad de consumo eléctrico.
        self.assertIn("kWh", respuesta)

    # ========================================================
    # 2. CÁLCULO PROVISIONAL DE EMISIONES
    # ========================================================

    def test_calculo_provisional(self):
        """Verifica el cálculo y su almacenamiento provisional."""

        # Se calcula el resultado utilizando los datos ficticios:
        # 2000 kWh × 0.2 kgCO2e/kWh = 400 kgCO2e.
        respuesta = hcp.calcular_emisiones_electricidad.func(
            **self.datos
        )

        # Se comprueba que el resultado aparezca en la respuesta.
        self.assertIn("400", respuesta)

        # Se identifica el último cálculo incorporado
        # a la memoria provisional del proceso.
        ultimo_id = hcp.ORDEN[-1]

        # Se verifica el valor numérico registrado.
        self.assertEqual(
            hcp.CALCULOS[ultimo_id]["emisiones_kgco2e"],
            400,
        )

        # Se comprueba que calcular no produzca
        # automáticamente un registro persistente.
        self.assertFalse(
            (hcp.CARPETA_DATOS / "registros_hcp.jsonl").exists()
        )

    # ========================================================
    # 3. VALIDACIÓN DE VALORES NEGATIVOS
    # ========================================================

    def test_validacion_negativos(self):
        """Verifica el rechazo de consumos eléctricos negativos."""

        # Se reemplaza el consumo válido por un valor negativo.
        datos_invalidos = {
            **self.datos,
            "consumo_kwh": -1,
        }

        # Se invoca la herramienta mediante la interfaz
        # de LangChain para aplicar su esquema Pydantic.
        with self.assertRaises(ValidationError):
            hcp.calcular_emisiones_electricidad.invoke(
                datos_invalidos
            )

    # ========================================================
    # 4. RECHAZO DE GUARDADO
    # ========================================================

    def test_rechazo_no_guarda(self):
        """Verifica que un rechazo impida el guardado persistente."""

        # Se genera un cálculo provisional.
        hcp.calcular_emisiones_electricidad.func(**self.datos)

        # Se simula una decisión humana negativa.
        # La función original no solicita entrada por terminal.
        with patch.object(
            hcp,
            "esperar_aprobacion",
            return_value=False,
        ):
            respuesta = hcp.guardar_calculo_hcp.func("ultimo")

        # Se comprueba que la herramienta informe el rechazo.
        self.assertIn("rechazado", respuesta)

        # Se verifica que no exista un archivo
        # con cálculos confirmados.
        self.assertFalse(
            (hcp.CARPETA_DATOS / "registros_hcp.jsonl").exists()
        )

        # Se consulta el registro de decisiones humanas.
        aprobaciones = hcp.leer_jsonl(
            hcp.CARPETA_DATOS / "aprobaciones_hcp.jsonl"
        )

        # Se comprueba que la decisión haya quedado registrada
        # como una aprobación negativa.
        self.assertFalse(aprobaciones[0]["aprobado"])

    # ========================================================
    # 5. APROBACIÓN Y PREVENCIÓN DE DUPLICADOS
    # ========================================================

    def test_aprobacion_guarda_sin_duplicar(self):
        """Verifica el guardado autorizado y evita duplicados."""

        # Se genera un cálculo provisional.
        hcp.calcular_emisiones_electricidad.func(**self.datos)

        # Se simula una aprobación humana afirmativa.
        with patch.object(
            hcp,
            "esperar_aprobacion",
            return_value=True,
        ):

            # Se realiza el primer intento de guardado.
            respuesta = hcp.guardar_calculo_hcp.func("ultimo")

            # Se intenta guardar nuevamente el mismo cálculo.
            respuesta_duplicada = (
                hcp.guardar_calculo_hcp.func("ultimo")
            )

        # Se comprueba que el primer guardado sea exitoso.
        self.assertIn("guardado correctamente", respuesta)

        # Se verifica que el segundo intento sea identificado
        # como una operación ya realizada.
        self.assertIn("ya fue guardado", respuesta_duplicada)

        # Se consultan los cálculos almacenados.
        registros = hcp.leer_jsonl(
            hcp.CARPETA_DATOS / "registros_hcp.jsonl"
        )

        # Se consultan las decisiones humanas registradas.
        aprobaciones = hcp.leer_jsonl(
            hcp.CARPETA_DATOS / "aprobaciones_hcp.jsonl"
        )

        # Se verifica que solo exista un cálculo guardado.
        self.assertEqual(len(registros), 1)

        # Se verifica que el segundo intento no haya generado
        # una nueva solicitud de aprobación.
        self.assertEqual(len(aprobaciones), 1)

    # ========================================================
    # 6. TRAZABILIDAD DE ARGUMENTOS
    # ========================================================

    def test_traza_con_argumentos(self):
        """Verifica el registro de argumentos de una herramienta."""

        # Se construye una respuesta simulada del ejecutor.
        # SimpleNamespace representa la acción de una herramienta
        # sin necesidad de ejecutar el modelo Gemini.
        resultado = {
            "output": "400 kgCO2e",
            "intermediate_steps": [
                (
                    SimpleNamespace(
                        tool="calcular_emisiones_electricidad",
                        tool_input=self.datos,
                    ),
                    "400",
                )
            ],
        }

        # Se registra la traza de la ejecución simulada.
        hcp.registrar_traza(
            "prueba_A",
            "calcula",
            resultado,
        )

        # Se recupera la primera traza almacenada.
        traza = hcp.leer_jsonl(
            hcp.CARPETA_DATOS / "trazas_hcp.jsonl"
        )[0]

        # Se comprueba que el consumo eléctrico quede
        # registrado dentro de los argumentos de la acción.
        self.assertEqual(
            traza["acciones"][0]["argumentos"]["consumo_kwh"],
            2000,
        )

    # ========================================================
    # 7. TIEMPO LÍMITE DE APROBACIÓN
    # ========================================================

    def test_timeout_rechaza(self):
        """Verifica el rechazo cuando vence el plazo de aprobación."""

        # Se crea un evento para controlar una respuesta simulada.
        desbloquear = threading.Event()

        def respuesta_tardia(*_args, **_kwargs):
            """Simula una aprobación que llega fuera del plazo."""

            # La respuesta permanece bloqueada hasta que
            # se active el evento o transcurra un segundo.
            desbloquear.wait(1)

            return "s"

        try:
            # Se simula una terminal interactiva y se reemplaza
            # input() por la función de respuesta tardía.
            with (
                patch.object(hcp.sys, "stdin") as stdin,
                patch(
                    "builtins.input",
                    side_effect=respuesta_tardia,
                ),
            ):

                stdin.isatty.return_value = True

                # Se establece un plazo de 0.02 segundos,
                # inferior al tiempo de la respuesta simulada.
                aprobado = hcp.esperar_aprobacion(
                    "¿Aprueba? ",
                    0.02,
                )

                # Se verifica que el tiempo agotado
                # produzca una decisión negativa.
                self.assertFalse(aprobado)

                # Se comprueba que el sistema identifique
                # explícitamente el vencimiento del plazo.
                self.assertTrue(hcp.APROBACION_AGOTADA)

        finally:
            # Se libera la función de entrada simulada
            # para evitar dejar una espera activa.
            desbloquear.set()

    # ========================================================
    # 8. MENSAJE COMPRENSIBLE ANTE ERROR DE VALIDACIÓN
    # ========================================================

    def test_error_validacion_mensaje_comprensible(self):
        """
        Verifica que un error de Pydantic se comunique
        con claridad y quede registrado en las trazas.
        """

        # Se construye un error real de validación
        # utilizando un consumo eléctrico negativo.
        with self.assertRaises(ValidationError) as contexto:
            hcp.ArgumentosElectricidad(
                consumo_kwh=-500,
                factor_kgco2e_kwh=0.3,
                proceso="fabricación de engranajes",
                periodo="septiembre de 2026",
            )

        # Se configura un agente simulado cuya invocación
        # genera el error de validación anterior.
        agente_simulado = Mock()
        agente_simulado.invoke.side_effect = contexto.exception

        # Se utiliza un buffer de texto para capturar
        # los mensajes mostrados por ejecutar_turno().
        salida = StringIO()

        with redirect_stdout(salida):

            # Se ejecuta el turno simulado.
            # La carpeta temporal ya fue configurada
            # mediante el método setUp().
            hcp.ejecutar_turno(
                agente_simulado,
                "Calcula emisiones con -500 kWh",
            )

        # Se recupera el texto presentado al usuario.
        mensaje = salida.getvalue()

        # Se verifica que aparezca un encabezado comprensible
        # en lugar de mostrar únicamente la excepción técnica.
        self.assertIn(
            "DATOS NO VÁLIDOS",
            mensaje,
        )

        # Se comprueba que el mensaje identifique
        # el campo que contiene el valor incorrecto.
        self.assertIn(
            "El campo 'consumo_kwh' debe ser mayor o igual a",
            mensaje,
        )

        # Se identifica el archivo de trazabilidad
        # creado en la carpeta temporal de la prueba.
        ruta_traza = (
            hcp.CARPETA_DATOS / "trazas_hcp.jsonl"
        )

        # Se verifica la existencia del archivo.
        self.assertTrue(ruta_traza.exists())

        # Se recupera el registro JSONL generado
        # durante la ejecución del escenario.
        registro = json.loads(
            ruta_traza.read_text(
                encoding="utf-8"
            ).strip()
        )

        # Se comprueba que el turno haya sido registrado
        # como una ejecución con error.
        self.assertEqual(
            registro["estado"],
            "error",
        )

        # Se verifica que la traza conserve
        # el tipo técnico de la excepción.
        self.assertEqual(
            registro["tipo_error"],
            "ValidationError",
        )


# ============================================================
# EJECUCIÓN DIRECTA DE LAS PRUEBAS
# ============================================================

if __name__ == "__main__":

    # Se ejecutan las pruebas cuando el archivo
    # se inicia directamente desde Python.
    unittest.main(verbosity=2)
