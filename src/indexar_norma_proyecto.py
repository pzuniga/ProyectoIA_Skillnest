"""Adaptador del corpus NCh-ISO 14067 al rag_indexer_proyecto del curso Skillnest.

Ejecutar desde C:\\ProyectoIA_Skillnest:
    python -m src.indexar_norma_proyecto
    python -m src.indexar_norma_proyecto --indexar --permiso-api

Por defecto SÓLO inspecciona los chunks localmente: NO utiliza Gemini.
En modo --indexar usa el flujo de la profesora (Gemini Embeddings + Chroma).
No contiene ni exporta texto de la norma.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .preparar_norma import PROJECT_ROOT, cargar_corpus_json
from .rag_indexer_proyecto import preparar_chunks, cargar_vectorstore, verificar_integridad
from .indexacion_lotes_proyecto import indexar_lotes

RUTA_CORPUS = PROJECT_ROOT / 'data' / 'corpus' / 'nch_iso_14067_2019.json'


def cargar_documentos_con_ids(ruta_corpus: Path):
    """Valida SHA del JSON con cargar_corpus_json() y recupera los IDs originales."""
    documentos = cargar_corpus_json(ruta_corpus)
    contenido = json.loads(ruta_corpus.read_text(encoding='utf-8'))
    registros = contenido['documentos']
    if len(documentos) != len(registros):
        raise ValueError('Número de documentos no coincide con el JSON')
    for doc, registro in zip(documentos, registros):
        if (doc.page_content != registro['page_content'] or
                doc.metadata != registro['metadata']):
            raise ValueError('Desajuste entre documentos validados y los registros')
        if not isinstance(registro.get('id'), str) or not registro['id']:
            raise ValueError('Registro sin ID persistente')
        doc.metadata['unidad_id'] = registro['id']
    if len({d.metadata['unidad_id'] for d in documentos}) != len(documentos):
        raise ValueError('IDs de unidades repetidos')
    return documentos, contenido


def inspeccionar_corpus(documentos, chunk_size: int, chunk_overlap: int):
    chunks, ids = preparar_chunks(
        documentos, chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        es_documento=True,
    )
    if not chunks or not ids or len(chunks) != len(ids):
        raise ValueError('Faltan chunks o IDs en la preparación')
    tipos = {}
    visuales_indivisibles = 0
    for chunk in chunks:
        tipo = chunk.metadata.get('tipo_contenido', 'desconocido')
        tipos[tipo] = tipos.get(tipo, 0) + 1
        if tipo in {'figura','tabla_fila','tabla_resumen'}:
            visuales_indivisibles += 1
    resumen = {
        'documentos_originales': len(documentos),
        'chunks_total': len(chunks),
        'ids_chunks_unicos': len(set(ids)),
        'chunk_size': chunk_size,
        'chunk_overlap': chunk_overlap,
        'chunks_por_tipo': dict(sorted(tipos.items())),
        'chunks_visuales_indivisibles': visuales_indivisibles,
        'longitud_maxima_chunk': max(len(c.page_content) for c in chunks),
    }
    return resumen


def main():
    parser = argparse.ArgumentParser(description='Preparar y, opcionalmente, indexar el corpus normativo en Chroma')
    parser.add_argument('--corpus', type=Path, default=RUTA_CORPUS)
    parser.add_argument('--chunk-size', type=int, default=600)
    parser.add_argument('--chunk-overlap', type=int, default=90)
    parser.add_argument('--indexar', action='store_true', help='Genera embeddings remotos y guarda Chroma')
    parser.add_argument('--permiso-api', action='store_true', help='Confirma autorización para transmitir el corpus a Gemini')
    parser.add_argument('--estado', action='store_true', help='Consulta cuántos chunks existen en Chroma sin llamar a Gemini')
    parser.add_argument('--reanudar', action='store_true', help='Reanuda una indexación parcial; no duplica IDs')
    parser.add_argument('--tamano-lote', type=int, default=30, help='Cantidad de chunks por lote (predeterminado 30)')
    parser.add_argument('--pausa', type=float, default=35, help='Pausa entre lotes en segundos (predeterminado 35)')
    args = parser.parse_args()

    ruta_corpus = args.corpus.resolve()
    documentos, informacion = cargar_documentos_con_ids(ruta_corpus)
    resumen = inspeccionar_corpus(documentos, args.chunk_size, args.chunk_overlap)
    resumen['corpus_sha256'] = informacion['corpus_sha256']
    resumen['pdf_sha256'] = informacion['pdf_sha256']
    directorio_vs = PROJECT_ROOT / f'vectorstore_iso14067_cs{args.chunk_size}_ov{args.chunk_overlap}'
    resumen['vectorstore'] = str(directorio_vs)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))

    if args.estado:
        if directorio_vs.exists() and any(directorio_vs.iterdir()):
            vs_estado = cargar_vectorstore(str(directorio_vs))
            existentes = set(vs_estado.get(include=[])["ids"])
        else:
            existentes = set()
        chunks_esperados, ids_esperados = preparar_chunks(
            documentos, chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap, es_documento=True,
        )
        desconocidos = existentes - set(ids_esperados)
        print(json.dumps({
            "guardados": len(existentes),
            "esperados": len(chunks_esperados),
            "pendientes": len(set(ids_esperados) - existentes),
            "ids_ajenos": len(desconocidos),
        }, ensure_ascii=False, indent=2))
        return

    if not args.indexar:
        print('MODO LOCAL: sólo se prepararon los chunks. No se consumió Gemini ni se creó Chroma.')
        print('Para inspeccionar lo existente: python -m src.indexar_norma_proyecto --estado')
        print('Para indexar: python -m src.indexar_norma_proyecto --indexar --permiso-api')
        print('Para continuar una indexación parcial: python -m src.indexar_norma_proyecto --indexar --reanudar --permiso-api')
        return

    if not args.permiso_api:
        parser.error('Antes de enviar texto protegido a Gemini, verifica tu licencia y usa --permiso-api si estás autorizado')
    if args.tamano_lote <= 0 or args.pausa < 0:
        parser.error('--tamano-lote debe ser > 0 y --pausa debe ser >= 0')

    existe_vs = directorio_vs.exists() and any(directorio_vs.iterdir())
    if existe_vs and not args.reanudar:
        parser.error(f'Ya existe un vectorstore en {directorio_vs}. Usa --estado y, si corresponde, --reanudar.')
    if args.reanudar and not existe_vs:
        parser.error(f'No hay vectorstore previo en {directorio_vs}; ejecuta sin --reanudar para crearlo.')

    chunks, ids = preparar_chunks(
        documentos, chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap, es_documento=True,
    )
    verificar_integridad(chunks, [d.page_content for d in documentos])
    directorio_vs.mkdir(parents=True, exist_ok=True)
    vs = cargar_vectorstore(str(directorio_vs))
    num_indexados = indexar_lotes(
        vectorstore=vs,
        documentos=chunks,
        ids=ids,
        tamano_lote=args.tamano_lote,
        pausa_segundos=args.pausa,
    )
    if num_indexados != resumen['chunks_total']:
        raise RuntimeError(f'Indexación parcial: Chroma tiene {num_indexados} chunks y se esperaban {resumen["chunks_total"]}')
    print(f'Indexación terminada: {num_indexados} chunks persistidos en {directorio_vs}')

if __name__ == '__main__':
    main()
