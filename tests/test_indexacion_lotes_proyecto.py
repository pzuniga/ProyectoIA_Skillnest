import unittest
from src.indexacion_lotes_proyecto import indexar_lotes, _espera_recomendada

class FalsoChroma:
    def __init__(self, almacenados=(), fallar_una_vez=False):
        self.ids = set(almacenados)
        self.fallar_una_vez = fallar_una_vez
        self.lotes = []
    def get(self, include=None):
        return {"ids": sorted(self.ids)}
    def add_documents(self, documents, ids):
        if self.fallar_una_vez:
            self.fallar_una_vez = False
            raise RuntimeError("429 RESOURCE_EXHAUSTED Please retry in 33.45s")
        self.ids.update(ids)
        self.lotes.append((len(documents), len(ids)))

class PruebasLotes(unittest.TestCase):
    def test_inicia_vacio_y_termina(self):
        vs=FalsoChroma()
        indexar_lotes(vs, list(range(7)), [str(i) for i in range(7)], tamano_lote=3,
                      pausa_segundos=1, dormir=lambda _: None, informar=lambda _:None)
        self.assertEqual(vs.ids, {str(i) for i in range(7)})
        self.assertEqual(vs.lotes, [(3,3),(3,3),(1,1)])
    def test_reanuda_sin_repetir(self):
        vs=FalsoChroma(['0','1'])
        indexar_lotes(vs,list(range(4)),[str(i) for i in range(4)], tamano_lote=3,
                      pausa_segundos=0, dormir=lambda _:None, informar=lambda _:None)
        self.assertEqual(vs.lotes, [(2,2)])
    def test_retry_429(self):
        vs=FalsoChroma(fallar_una_vez=True)
        esperas=[]
        indexar_lotes(vs,['d1'],['1'], pausa_segundos=0,
                      dormir=esperas.append, informar=lambda _:None)
        self.assertEqual(len(esperas),1)
        self.assertGreaterEqual(esperas[0],70)
    def test_impide_ids_ajenos(self):
        with self.assertRaises(ValueError):
            indexar_lotes(FalsoChroma(['otro']),['d1'],['1'],
                          dormir=lambda _:None, informar=lambda _:None)
    def test_reintentos_limitados(self):
        self.assertEqual(_espera_recomendada(RuntimeError('429 Please retry in 80s')), 82)

if __name__ == '__main__':
    unittest.main()
