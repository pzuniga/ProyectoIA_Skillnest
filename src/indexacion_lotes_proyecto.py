"""Carga incremental y reanudable de documentos en un Chroma ya configurado.

Este módulo es independiente de Gemini y LangChain para facilitar pruebas locales.
No crea embeddings por sí solo: delega en vectorstore.add_documents().
"""
from __future__ import annotations

import re
import time
from typing import Callable


def _espera_recomendada(error: Exception, minimo: float = 70) -> float:
    """Respeta la indicación 'retry in Ns' si supera la pausa conservadora."""
    mensaje = str(error)
    coinc = re.search(r"(?:Please\s+)?retry\s+in\s+([0-9]+(?:\.[0-9]+)?)s", mensaje, re.I)
    return max(minimo, float(coinc.group(1)) + 2 if coinc else minimo)


def indexar_lotes(
    vectorstore,
    documentos,
    ids: list[str],
    tamano_lote: int = 30,
    pausa_segundos: float = 35,
    max_reintentos_429: int = 4,
    dormir: Callable[[float], None] = time.sleep,
    informar: Callable[[str], None] = print,
) -> int:
    """Indexa únicamente los IDs faltantes y se recupera de un error 429.

    Revisa los IDs en Chroma antes de cada intento para evitar duplicaciones
    incluso si un lote quedó parcialmente persistido antes de fallar.
    """
    if not documentos or len(documentos) != len(ids):
        raise ValueError("Se requieren documentos e IDs del mismo largo, no vacíos")
    if len(ids) != len(set(ids)):
        raise ValueError("Los IDs de los chunks contienen duplicados")
    if tamano_lote <= 0 or pausa_segundos < 0 or max_reintentos_429 < 0:
        raise ValueError("Parámetros de lotes o esperas inválidos")

    def ids_guardados() -> set[str]:
        return set(vectorstore.get(include=[])["ids"])

    existentes = ids_guardados()
    ids_esperados = set(ids)
    ajenos = existentes - ids_esperados
    if ajenos:
        raise ValueError(
            f"Chroma contiene {len(ajenos)} IDs que no pertenecen a este corpus/configuración. "
            "No se modificará la colección."
        )

    pendientes = [(ident, doc) for ident, doc in zip(ids, documentos) if ident not in existentes]
    informar(f"Chroma: {len(existentes)} existentes / {len(pendientes)} pendientes / {len(ids)} esperados")
    if not pendientes:
        return len(existentes)

    lotes = [pendientes[i:i + tamano_lote] for i in range(0, len(pendientes), tamano_lote)]
    for numero, lote in enumerate(lotes, start=1):
        fallos_429 = 0
        while True:
            guardados = ids_guardados()
            faltantes_lote = [(ident, doc) for ident, doc in lote if ident not in guardados]
            if not faltantes_lote:
                break
            try:
                vectorstore.add_documents(
                    documents=[doc for _, doc in faltantes_lote],
                    ids=[ident for ident, _ in faltantes_lote],
                )
                break
            except Exception as error:
                texto_error = str(error)
                if "429" not in texto_error and "RESOURCE_EXHAUSTED" not in texto_error:
                    raise
                fallos_429 += 1
                if fallos_429 > max_reintentos_429:
                    raise RuntimeError(
                        f"El lote {numero} alcanzó el máximo de reintentos por cuota. "
                        "Los lotes completados quedan en Chroma; reanuda posteriormente."
                    ) from error
                espera = _espera_recomendada(error)
                informar(f"Lote {numero}: cuota 429; reintento {fallos_429}/{max_reintentos_429} tras {espera:g}s")
                dormir(espera)

        informar(f"Lote {numero}/{len(lotes)}: {len(ids_guardados())}/{len(ids)} chunks persistidos")
        if numero < len(lotes) and pausa_segundos:
            dormir(pausa_segundos)

    final = ids_guardados()
    if final != ids_esperados:
        raise RuntimeError(f"Indexación incompleta: faltan {len(ids_esperados - final)} IDs")
    informar(f"Indexación completa: {len(final)} chunks únicos")
    return len(final)
