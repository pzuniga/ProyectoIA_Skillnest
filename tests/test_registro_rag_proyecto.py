"""Pruebas locales sin llamadas a Gemini ni Chroma real.

python -m unittest discover -s tests -p "test_registro_rag_proyecto.py" -v
"""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.registro_rag_proyecto import (
    PROMPT_TEMPLATE,
    PREGUNTAS_ACTIVIDAD,
    calcular_costo,
    formatear_contexto,
    guardar_registro_jsonl,
    registrar_consulta,
    _plan_ejecucion,
)


class Doc:
    def __init__(self, apartado, identificador, texto):
        self.id = identificador
        self.page_content = texto
        self.metadata = {
            "fuente": "NCh-ISO 14067:2019", "apartado": apartado,
            "tipo_contenido": "apartado", "pagina_pdf_inicio": 31,
            "pagina_norma_inicio": 19,
        }


class Retriever:
    def __init__(self, documentos, parent):
        self.documentos = documentos
        self.parent = parent

    def invoke(self, pregunta):
        self.parent.preguntas.append(pregunta)
        return self.documentos[: self.parent.k]


class VS:
    def __init__(self):
        self.preguntas = []
        self.k = None
        self.documentos = [
            Doc("6.3.5", "id_a", "Datos secundarios se justifican."),
            Doc("6.4.6.2", "id_b", "Asignar cargas entre productos."),
            Doc("7.3", "id_c", "El informe documenta el estudio."),
            Doc("6.4.9.4.4", "id_d", "Electricidad de red."),
            Doc("6.3.4.3", "id_e", "Criterios de corte."),
            Doc("3.1.1", "id_f", "Definición."),
        ]

    def as_retriever(self, search_kwargs):
        self.k = search_kwargs["k"]
        return Retriever(self.documentos, self)


class Modelo:
    def __init__(self, metadata=None):
        self.prompts = []
        self.metadata = metadata

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content="Respuesta sustentada [1].", usage_metadata=self.metadata)


class PruebasRegistroRag(unittest.TestCase):
    def test_mide_tres_etapas_y_calcula_costo(self):
        reloj = iter([0, .1, .1, .2, .2, .8]).__next__
        m = Modelo({"input_tokens": 1000, "output_tokens": 200, "total_tokens": 1200})
        r = registrar_consulta(VS(), "¿Qué dicen los datos?", 3, chat_model=m, reloj=reloj)
        self.assertEqual(r["tiempos_ms"], {"embed_y_busqueda": 100, "armado_prompt": 100, "generacion": 600})
        self.assertEqual(r["tiempo_total_ms"], 800)
        self.assertEqual(r["tokens"]["input_tokens"], 1000)
        self.assertEqual(r["costo_estimado_usd"], .0008)
        self.assertIn("[1]", m.prompts[0])
        self.assertIn("6.3.5", m.prompts[0])
        self.assertEqual(r["ids_recuperados"], ["id_a", "id_b", "id_c"])

    def test_k6_incluye_mas_contexto(self):
        v = VS()
        m = Modelo({"input_tokens": 300, "output_tokens": 20})
        tres = registrar_consulta(v, "¿Pregunta?", 3, m)
        seis = registrar_consulta(v, "¿Pregunta?", 6, m)
        self.assertEqual(tres["chunks_recuperados"], 3)
        self.assertEqual(seis["chunks_recuperados"], 6)
        self.assertEqual(len(m.prompts), 2)
        self.assertGreater(len(m.prompts[1]), len(m.prompts[0]))

    def test_sin_tokens_no_inventa_costo(self):
        r = registrar_consulta(VS(), "Pregunta", 3, Modelo(None))
        self.assertIsNone(r["tokens"])
        self.assertIsNone(r["costo_estimado_usd"])

    def test_jsonl_anexa_y_no_guarda_respuesta_por_defecto(self):
        r = registrar_consulta(VS(), "Pregunta", 3, Modelo({"input_tokens": 10, "output_tokens": 5}))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "registro.jsonl"
            guardar_registro_jsonl(r, p)
            guardar_registro_jsonl(r, p)
            lineas = p.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lineas), 2)
            r2 = json.loads(lineas[0])
            self.assertNotIn("respuesta_generada", r2)
            self.assertTrue(all(k in r2 for k in ("timestamp", "pregunta", "k", "tiempos_ms", "tiempo_total_ms", "tokens")))

    def test_guardar_respuesta_activado(self):
        r = registrar_consulta(VS(), "Pregunta", 3, Modelo(None))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "registro.jsonl"
            guardar_registro_jsonl(r, p, guardar_respuesta=True)
            self.assertIn("respuesta_generada", json.loads(p.read_text(encoding="utf-8")))

    def test_citas_reales_en_contexto(self):
        contexto, citas = formatear_contexto([Doc("6.4.6.2", "a", "Texto de ejemplo")])
        self.assertIn("Apartado: 6.4.6.2", contexto)
        self.assertIn("Página norma: 19", contexto)
        self.assertEqual(citas["1"]["id_chunk"], "a")
        self.assertIn("{contexto}", PROMPT_TEMPLATE)

    def test_plan_actividad_y_comparacion(self):
        args = SimpleNamespace(actividad_core=True, pregunta=None, comparar=False, k=3)
        plan = _plan_ejecucion(args)
        self.assertEqual(len(plan), 4)
        self.assertEqual(plan[-1], (PREGUNTAS_ACTIVIDAD[0], 6))
        args = SimpleNamespace(actividad_core=False, pregunta=["Pregunta"], comparar=True, k=3)
        self.assertEqual(_plan_ejecucion(args), [("Pregunta", 3), ("Pregunta", 6)])

    def test_no_llama_modelo_sin_chuncks(self):
        v = VS()
        v.documentos = []
        m = Modelo(None)
        with self.assertRaises(ValueError):
            registrar_consulta(v, "Pregunta", 3, m)
        self.assertEqual(m.prompts, [])

    def test_validaciones_costo(self):
        self.assertAlmostEqual(calcular_costo(1_000_000, 1_000_000), 2.8)
        with self.assertRaises(ValueError):
            calcular_costo(-1, 2)
        with self.assertRaises(ValueError):
            registrar_consulta(VS(), "", 3, Modelo(None))
        with self.assertRaises(ValueError):
            registrar_consulta(VS(), "Pregunta", 0, Modelo(None))


if __name__ == "__main__":
    unittest.main()
