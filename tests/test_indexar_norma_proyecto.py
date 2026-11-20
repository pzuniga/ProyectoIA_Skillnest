"""Pruebas locales de chunking e IDs; no llaman a Gemini ni crean Chroma.

Para ejecutarlas desde la raíz, con dependencias del curso instaladas:
    python -m unittest discover -s tests -p "test_indexar_norma_proyecto.py" -v
"""
from pathlib import Path
import unittest

CORPUS = Path(__file__).resolve().parents[1] / 'data' / 'corpus' / 'nch_iso_14067_2019.json'
try:
    from src.indexar_norma_proyecto import cargar_documentos_con_ids, inspeccionar_corpus
    from src.rag_indexer_proyecto import preparar_chunks
    DEPENDENCIAS_INSTALADAS = True
except ImportError:
    DEPENDENCIAS_INSTALADAS = False


@unittest.skipUnless(DEPENDENCIAS_INSTALADAS and CORPUS.exists(),
                     'Se requieren LangChain y el corpus JSON local validado')
class TestIndexacionNorma(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs, cls.info = cargar_documentos_con_ids(CORPUS)

    def test_141_documentos_con_ids(self):
        self.assertEqual(len(self.docs), 141)
        self.assertEqual(len({d.metadata['unidad_id'] for d in self.docs}), 141)

    def test_chunks_deterministas(self):
        uno, ids1 = preparar_chunks(self.docs, 600, 90, es_documento=True)
        dos, ids2 = preparar_chunks(self.docs, 600, 90, es_documento=True)
        self.assertEqual(ids1, ids2)
        self.assertEqual(len(uno), len(ids1))
        self.assertEqual(len(ids1), len(set(ids1)))

    def test_no_dividir_elementos_visuales(self):
        chunks, _ = preparar_chunks(self.docs, 600, 90, es_documento=True)
        visuales = [c for c in chunks if c.metadata.get('tipo_contenido')
                    in {'figura', 'tabla_fila', 'tabla_resumen'}]
        self.assertEqual(len(visuales), 10)
        self.assertEqual(sum(c.metadata.get('tipo_contenido') == 'tabla_fila'
                             for c in visuales), 6)
        self.assertTrue(all(c.metadata.get('chunk_orden') == 0 for c in visuales))

    def test_inspeccion_sin_api(self):
        r = inspeccionar_corpus(self.docs, 600, 90)
        self.assertEqual(r['documentos_originales'], 141)
        self.assertEqual(r['chunks_total'], r['ids_chunks_unicos'])
        self.assertEqual(r['chunks_visuales_indivisibles'], 10)


if __name__ == '__main__':
    unittest.main()
