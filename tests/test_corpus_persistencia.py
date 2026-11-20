"""Pruebas de persistencia local. Nunca genera embeddings ni llama a APIs.

La aprobación automática aquí es SOLO una simulación de prueba; en producción
las aprobaciones deben provenir de revisión humana válida.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
import types

from src.preparar_norma import (
    RUTA_NORMA, preparar_norma, plantilla_revision_visuales,
    construir_corpus_serializable, exportar_corpus_json, cargar_corpus_json,
)


@unittest.skipUnless(RUTA_NORMA.exists(), "Se necesita el PDF local en docs/Biblioteca")
class TestPersistenciaCorpus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf = RUTA_NORMA
        cls.resultado = preparar_norma(cls.pdf)

    def test_no_exportar_sin_aprobaciones(self):
        with tempfile.TemporaryDirectory() as d:
            destino = Path(d) / "corpus.json"
            with self.assertRaisesRegex(ValueError, "sin aprobación válida"):
                exportar_corpus_json(self.resultado, self.pdf, destino)
            self.assertFalse(destino.exists())

    def test_no_exportar_con_aprobaciones_parciales(self):
        r = preparar_norma(self.pdf)
        revisiones = plantilla_revision_visuales(r)
        revisiones["figura_1"]["aprobado"] = True
        self.assertFalse(r.aprobar_visuales(revisiones))
        with self.assertRaisesRegex(ValueError, "Figura 2"):
            construir_corpus_serializable(r, self.pdf)

    def _resultado_de_prueba_aprobado(self):
        # Simulación para TESTS. Nunca es una aprobación de producción.
        r = preparar_norma(self.pdf)
        revisiones = plantilla_revision_visuales(r)
        for elemento in revisiones.values():
            elemento["aprobado"] = True
        self.assertFalse(r.aprobar_visuales(revisiones))
        return r

    def test_exportar_141_y_metadatos(self):
        r = self._resultado_de_prueba_aprobado()
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "corpus.json"
            resumen = exportar_corpus_json(r, self.pdf, ruta)
            data = json.loads(ruta.read_text(encoding="utf-8"))
            self.assertEqual(resumen["documentos_total"], 141)
            self.assertEqual(data["estadisticas"]["documentos_texto"], 131)
            self.assertEqual(data["estadisticas"]["documentos_visuales"], 10)
            self.assertEqual(data["estadisticas"]["figuras_aprobadas"], 3)
            self.assertEqual(data["estadisticas"]["tablas_aprobadas"], 1)
            self.assertEqual(len({d["id"] for d in data["documentos"]}), 141)
            self.assertEqual(len(data["pdf_sha256"]), 64)
            self.assertTrue(all(d["page_content"].strip() for d in data["documentos"]))
            self.assertTrue(all("apartado" in d["metadata"] for d in data["documentos"]))
            self.assertEqual(
                sum(d["metadata"]["tipo_contenido"] == "tabla_fila" for d in data["documentos"]),
                6,
            )

    def test_ids_estables_entre_preparaciones(self):
        r = self._resultado_de_prueba_aprobado()
        uno = construir_corpus_serializable(r, self.pdf)
        dos = construir_corpus_serializable(r, self.pdf)
        self.assertEqual([x["id"] for x in uno["documentos"]],
                         [x["id"] for x in dos["documentos"]])
        self.assertEqual(uno["corpus_sha256"], dos["corpus_sha256"])

    def test_cargar_y_detectar_manipulacion(self):
        r = self._resultado_de_prueba_aprobado()
        class FakeDocument:
            def __init__(self, page_content, metadata):
                self.page_content = page_content
                self.metadata = metadata
        fake_core = types.ModuleType("langchain_core")
        fake_docs = types.ModuleType("langchain_core.documents")
        fake_docs.Document = FakeDocument
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "corpus.json"
            exportar_corpus_json(r, self.pdf, ruta)
            with patch.dict(sys.modules, {"langchain_core": fake_core,
                                          "langchain_core.documents": fake_docs}):
                docs = cargar_corpus_json(ruta)
            self.assertEqual(len(docs), 141)
            self.assertIn("apartado", docs[0].metadata)
            data = json.loads(ruta.read_text(encoding="utf-8"))
            data["documentos"][0]["page_content"] = "contenido alterado"
            ruta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                cargar_corpus_json(ruta)


if __name__ == "__main__":
    unittest.main()
