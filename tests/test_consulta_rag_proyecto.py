"""Pruebas unitarias sin Gemini ni Chroma real.

Desde la raíz del proyecto:
    python -m unittest discover -s tests -p 'test_consulta_rag_proyecto.py' -v
"""
import json
import tempfile
import unittest
from pathlib import Path

from src.consulta_rag_proyecto import (
    comprobar_directorio_chroma,
    consultar,
    evaluar_apartados,
    comparar_k,
    guardar_reporte,
)


class DocumentoSimulado:
    def __init__(self, identificador, apartado, tipo="apartado", texto="Texto normativo"):
        self.id = identificador
        self.page_content = texto
        self.metadata = {
            "fuente": "NCh-ISO 14067:2019",
            "apartado": apartado,
            "titulo": "Título",
            "tipo_contenido": tipo,
            "pagina_pdf_inicio": 31,
            "pagina_pdf_fin": 32,
            "pagina_norma_inicio": 19,
            "pagina_norma_fin": 20,
        }


class ChromaSimulado:
    def __init__(self):
        self.llamadas = []
        self.documentos = [
            (DocumentoSimulado("c1", "6.3.5"), 0.11),
            (DocumentoSimulado("c2", "6.4.6.2"), 0.22),
            (DocumentoSimulado("c3", "7.3"), 0.33),
            (DocumentoSimulado("c4", "6.4.9.4.4"), 0.44),
            (DocumentoSimulado("c5", "6.4.9.5"), 0.55),
            (DocumentoSimulado("c6", "3.1.1.1"), 0.66),
        ]

    def similarity_search_with_score(self, query, k):
        self.llamadas.append((query, k))
        return self.documentos[:k]


class PruebasConsultaRag(unittest.TestCase):
    def test_consulta_k3_y_referencias(self):
        vs = ChromaSimulado()
        reloj = iter([10.0, 10.25]).__next__
        res = consultar(vs, "  ¿Datos secundarios?  ", 3, reloj=reloj)
        self.assertEqual(vs.llamadas, [("¿Datos secundarios?", 3)])
        self.assertEqual(res["recuperados"], 3)
        self.assertEqual(res["latencia_busqueda_ms"], 250.0)
        self.assertEqual(res["resultados"][0]["apartado"], "6.3.5")
        self.assertEqual(res["resultados"][0]["pagina_norma_inicio"], 19)

    def test_comparar_k3_y_k6(self):
        vs = ChromaSimulado()
        reloj = iter([0.0, 0.2, 1.0, 1.5]).__next__
        uno = consultar(vs, "Pregunta", 3, reloj=reloj)
        dos = consultar(vs, "Pregunta", 6, reloj=reloj)
        comp = comparar_k(uno, dos)
        self.assertEqual(comp["coincidencias_ids"], 3)
        self.assertEqual(comp["ids_adicionales_segundo"], 3)
        self.assertEqual(comp["latencia_primero_ms"], 200.0)
        self.assertEqual(comp["latencia_segundo_ms"], 500.0)

    def test_evaluacion_presencia_no_precision(self):
        res = consultar(ChromaSimulado(), "Pregunta", 3, reloj=lambda: 0.0)
        datos = evaluar_apartados(res, ["6.3.5"])
        self.assertTrue(datos["al_menos_un_apartado_esperado"])
        self.assertEqual(datos["apartados_esperados_recuperados"], ["6.3.5"])

    def test_no_acepta_pregunta_vacia_k_invalido(self):
        vs = ChromaSimulado()
        with self.assertRaises(ValueError):
            consultar(vs, " ")
        with self.assertRaises(ValueError):
            consultar(vs, "Pregunta", 0)
        self.assertFalse(vs.llamadas)

    def test_reporte_no_guarda_texto_del_pdf(self):
        res = consultar(ChromaSimulado(), "Pregunta", 3, mostrar_texto=True, reloj=lambda: 0.0)
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "salida.json"
            guardar_reporte(ruta, {"consultas": [res], "comparaciones": []})
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            self.assertNotIn("vista_previa_local", datos["consultas"][0]["resultados"][0])
            self.assertEqual(datos["consultas"][0]["resultados"][0]["id_chunk"], "c1")

    def test_comprueba_directorio_no_existente_sin_crear_chroma(self):
        with tempfile.TemporaryDirectory() as temp:
            ruta = Path(temp) / "sin_chroma"
            with self.assertRaises(FileNotFoundError):
                comprobar_directorio_chroma(ruta)
            self.assertFalse(ruta.exists())

    def test_apartado_fila_preferido(self):
        vs = ChromaSimulado()
        vs.documentos[0][0].metadata.update({"apartado": "6.4.9.8", "apartado_fila": "6.4.9.5"})
        r = consultar(vs, "CUSd", 1, reloj=lambda: 0)
        self.assertEqual(r["resultados"][0]["apartado"], "6.4.9.5")
        self.assertEqual(r["resultados"][0]["apartado_contenedor"], "6.4.9.8")


if __name__ == "__main__":
    unittest.main()
