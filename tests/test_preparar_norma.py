"""Pruebas del parser de normas y sus elementos visuales (sin usar APIs)."""
from pathlib import Path
import unittest
from unittest.mock import patch
import sys
import types

from src.preparar_norma import (
    RUTA_NORMA, preparar_norma, generar_diagnostico,
    normalizar_texto, plantilla_revision_visuales,
)

PDF = RUTA_NORMA


@unittest.skipUnless(PDF.exists(), "No se encuentra PDF de prueba en docs/Biblioteca")
class TestPrepararNorma(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = preparar_norma(PDF)
        cls.unidades = {u.apartado: u for u in cls.r.unidades}
        cls.visuales = {v.referencia: v for v in cls.r.elementos_visuales}

    def test_estructura_principal(self):
        for numero in map(str, range(1, 9)):
            self.assertIn(numero, self.unidades)
        for letra in "ABCDE":
            self.assertIn(f"Anexo {letra}", self.unidades)

    def test_ids_unicos(self):
        self.assertEqual(len(self.unidades), len(self.r.unidades))

    def test_apartado_entre_paginas(self):
        u = self.unidades["6.3.5"]
        self.assertEqual((u.pagina_pdf_inicio, u.pagina_pdf_fin), (31, 32))
        self.assertGreater(len(u.texto), 1000)

    def test_definicion_con_titulo_separado(self):
        u = self.unidades["3.1.1.1"]
        self.assertIn("huella de carbono", u.titulo)
        self.assertIn("HCP", u.titulo)
        self.assertIn("Nota 1", u.texto)

    def test_anexos_normativos_e_informativos(self):
        self.assertEqual(self.unidades["Anexo B"].caracter, "anexo_normativo")
        self.assertEqual(self.unidades["Anexo D"].caracter, "anexo_informativo")
        self.assertIn("productos", self.unidades["E.2"].titulo)

    def test_inventario_completo_tablas_figuras(self):
        self.assertEqual(set(self.visuales), {"Tabla 1", "Figura 1", "Figura 2", "Figura 3"})
        self.assertEqual(self.r.estadisticas["rotulos_visuales_detectados"], 4)
        self.assertEqual(self.r.estadisticas["figuras_procesadas"], 3)
        self.assertEqual(self.r.estadisticas["tablas_procesadas"], 1)
        self.assertFalse(self.r.estadisticas["visuales_con_error"])
        self.assertEqual(self.visuales["Figura 1"].pagina_norma, "x")
        self.assertEqual(self.visuales["Figura 2"].pagina_norma, "xii")
        self.assertEqual(self.visuales["Tabla 1"].apartado, "6.4.9.8")

    def test_tabla_marcadores_y_notas(self):
        tabla = self.visuales["Tabla 1"]
        self.assertEqual(len(tabla.filas), 6)
        self.assertEqual(tabla.filas[0]["apartado"], "6.4.9.2")
        self.assertIn("Debe estar incluido", tabla.filas[0]["columnas_marcadas"])
        self.assertEqual(len(tabla.filas[0]["columnas_marcadas"]), 2)
        self.assertIn("Debe ser considerado para la inclusión", tabla.filas[2]["columnas_marcadas"])
        self.assertIn("Debería estar incluido", tabla.filas[3]["columnas_marcadas"])
        self.assertEqual(len(tabla.filas[4]["columnas_marcadas"]), 1)
        self.assertIn("6.4.8", " ".join(tabla.notas))
        self.assertIn("CUSd (nota a)", tabla.filas[1]["concepto"])

    def test_figuras_con_etiquetas(self):
        for referencia in ("Figura 1", "Figura 2", "Figura 3"):
            figura = self.visuales[referencia]
            self.assertTrue(figura.descripcion)
            self.assertGreater(len(figura.texto_extraido), 100)
            self.assertFalse(figura.aprobado)
        self.assertIn("ISO 14064-1", self.visuales["Figura 1"].texto_extraido)
        self.assertIn("ISO 14067", self.visuales["Figura 2"].texto_extraido)
        self.assertIn("Carbono biogénico", self.visuales["Figura 3"].texto_extraido)

    def test_sin_duplicar_elementos_en_cuerpo(self):
        texto = self.unidades["6.4.9.8"].texto
        self.assertLess(len(texto), 800)
        self.assertNotIn("Carbón biogénico en los", texto)

    def test_bloqueo_y_aprobacion_con_hash(self):
        r = preparar_norma(PDF)
        revisiones = plantilla_revision_visuales(r)
        self.assertEqual(len(revisiones), 4)
        for item in revisiones.values():
            self.assertFalse(item["aprobado"])
        # Una aprobación con hash incorrecto no se acepta.
        revisiones["figura_1"]["aprobado"] = True
        revisiones["figura_1"]["sha256"] = "hash_desactualizado"
        errores = r.aprobar_visuales(revisiones)
        self.assertTrue(errores)
        self.assertFalse(r.elementos_visuales[0].aprobado)
        # Revisión correcta sí autoriza su incorporación al corpus.
        revisiones["figura_1"]["sha256"] = r.elementos_visuales[0].huella_sha256
        self.assertFalse(r.aprobar_visuales(revisiones))
        self.assertTrue(r.elementos_visuales[0].aprobado)

    def test_generacion_documentos_visuales_con_control(self):
        # Importación de LangChain simulada: solo verificamos la interfaz.
        mod_core = types.ModuleType("langchain_core")
        mod_docs = types.ModuleType("langchain_core.documents")
        class DocumentoPrueba:
            def __init__(self, page_content, metadata):
                self.page_content = page_content
                self.metadata = metadata
        mod_docs.Document = DocumentoPrueba
        with patch.dict(sys.modules, {"langchain_core": mod_core,
                                      "langchain_core.documents": mod_docs}):
            docs_sin_validar = self.r.documentos_langchain()
            self.assertEqual(len(docs_sin_validar), 131)
            docs_prueba = self.r.documentos_langchain(solo_visuales_aprobados=False)
        nuevos = docs_prueba[len(docs_sin_validar):]
        # 1 resumen de Tabla 1, 6 filas y 3 descripciones de figuras.
        self.assertEqual(len(nuevos), 10)
        self.assertEqual(len(docs_prueba), 141)
        self.assertTrue(all("referencia_visual" in d.metadata for d in nuevos))
        self.assertTrue(any(d.metadata["tipo_contenido"] == "tabla_fila" for d in nuevos))

    def test_sin_contaminacion_repetida(self):
        d = generar_diagnostico(self.r)
        self.assertFalse(d["controles"]["contaminacion_repetitiva_detectada_en_unidades"])
        self.assertTrue(d["controles"]["paginas_registradas_correctamente"])
        self.assertEqual(len(d["inventario_visual"]), 4)

    def test_normalizacion_controlada(self):
        self.assertEqual(normalizar_texto("cuantiﬁ cación"), "cuantificación")
        self.assertEqual(normalizar_texto("ﬂ ujos"), "flujos")
        self.assertEqual(normalizar_texto("debe / debería / puede"),
                         "debe / debería / puede")


if __name__ == "__main__":
    unittest.main()
