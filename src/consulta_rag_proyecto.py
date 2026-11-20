"""Consulta semántica de la NCh-ISO 14067:2019 ya indexada en Chroma.

Adaptación de la recuperación del curso (Chroma + Gemini Embeddings).
No genera respuestas con LLM, no modifica la base y no vuelve a indexar.

Ejemplos desde C:\\ProyectoIA_Skillnest:
    python -m src.consulta_rag_proyecto
    python -m src.consulta_rag_proyecto --pregunta "¿Qué criterios de corte se aplican?" --k 3
    python -m src.consulta_rag_proyecto --pregunta "¿Cuándo se usan datos secundarios?" --comparar
    python -m src.consulta_rag_proyecto --comparar --guardar

ATENCIÓN: cada consulta genera un embedding remoto de la pregunta y consume cuota.
La cuenta debe tener permiso para enviar el texto de la pregunta a Gemini.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VECTORSTORE_DEFAULT = PROJECT_ROOT / "vectorstore_iso14067_cs600_ov90"
REPORTE_DEFAULT = PROJECT_ROOT / "data" / "resultados" / "recuperacion_iso14067_proyecto.json"

# Preguntas de prueba basadas en los apartados del PDF original.
CASOS_PRUEBA = [
    {
        "pregunta": "¿En qué condiciones se pueden utilizar datos secundarios en un estudio de HCP?",
        "apartados_esperados": ["6.3.5"],
    },
    {
        "pregunta": "¿Cuál es el procedimiento de asignación entre coproductos?",
        "apartados_esperados": ["6.4.6.2"],
    },
    {
        "pregunta": "¿Qué requisitos existen para utilizar datos de un proveedor de electricidad de la red?",
        "apartados_esperados": ["6.4.9.4.4"],
    },
    {
        "pregunta": "¿Cómo se tratan las emisiones por cambio directo de uso del suelo?",
        "apartados_esperados": ["6.4.9.5"],
    },
    {
        "pregunta": "¿Qué información debe contener el informe de estudio de la HCP?",
        "apartados_esperados": ["7.3"],
    },
]


def comprobar_directorio_chroma(ruta: Path) -> None:
    """Impide que la apertura de Chroma cree accidentalmente un almacén vacío."""
    if not ruta.is_dir() or not (ruta / "chroma.sqlite3").is_file():
        raise FileNotFoundError(
            f"No se encontró una base Chroma indexada en '{ruta}'. "
            "Comprueba la ruta y ejecuta primero 'python -m src.indexar_norma_proyecto --estado'."
        )


def cargar_indice(ruta: Path):
    """Utiliza exactamente el mismo cargador de Chroma/embeddings que el curso."""
    comprobar_directorio_chroma(ruta)
    from .rag_indexer_proyecto import cargar_vectorstore
    vs = cargar_vectorstore(str(ruta))
    if not vs.get(include=[]).get("ids"):
        raise ValueError(f"La colección Chroma está vacía: {ruta}")
    return vs


def resumen_documento(doc, distancia: float, posicion: int, mostrar_texto: bool = False) -> dict[str, Any]:
    """Conserva referencias verificables; la distancia NO es probabilidad ni precisión."""
    meta = getattr(doc, "metadata", {}) or {}
    apartado = meta.get("apartado_fila") or meta.get("apartado") or "sin_apartado"
    pagina_pdf = meta.get("pagina_pdf_inicio", meta.get("pagina_pdf"))
    pagina_norma = meta.get("pagina_norma_inicio", meta.get("pagina_norma"))
    resultado = {
        "posicion": posicion,
        "id_chunk": getattr(doc, "id", None) or meta.get("unidad_id"),
        "distancia": round(float(distancia), 5),
        "fuente": meta.get("fuente", "desconocida"),
        "apartado": apartado,
        "apartado_contenedor": meta.get("apartado"),
        "titulo": meta.get("titulo", ""),
        "tipo_contenido": meta.get("tipo_contenido", "desconocido"),
        "caracter": meta.get("caracter", ""),
        "pagina_pdf_inicio": pagina_pdf,
        "pagina_pdf_fin": meta.get("pagina_pdf_fin", pagina_pdf),
        "pagina_norma_inicio": pagina_norma,
        "pagina_norma_fin": meta.get("pagina_norma_fin", pagina_norma),
    }
    if mostrar_texto:
        # Solo muestra una vista previa local para inspección; el JSON nunca incluye texto.
        resultado["vista_previa_local"] = " ".join(doc.page_content.split())[:300]
    return resultado


def consultar(
    vectorstore,
    pregunta: str,
    k: int = 3,
    mostrar_texto: bool = False,
    reloj: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """Consulta en Chroma igual que buscar_similares() de la profesora.

    similarity_search_with_score() incluye la vectorización remota de la pregunta.
    No se calcula el costo de embeddings porque este método no entrega tokens de uso.
    """
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise ValueError("La pregunta no puede estar vacía")
    if k < 1:
        raise ValueError("k debe ser >= 1")

    t0 = reloj()
    encontrados = vectorstore.similarity_search_with_score(query=pregunta.strip(), k=k)
    tiempo_ms = round((reloj() - t0) * 1000, 2)
    resultados = [
        resumen_documento(doc, distancia, i, mostrar_texto=mostrar_texto)
        for i, (doc, distancia) in enumerate(encontrados, start=1)
    ]
    return {
        "pregunta": pregunta.strip(),
        "k": k,
        "recuperados": len(resultados),
        "latencia_busqueda_ms": tiempo_ms,
        "resultados": resultados,
    }


def evaluar_apartados(resultado: dict[str, Any], apartados_esperados: list[str]) -> dict[str, Any]:
    """Control diagnóstico de presencia, NO reemplaza Precision@k/Recall@k por IDs."""
    encontrados = {r["apartado"] for r in resultado["resultados"]}
    return {
        "apartados_esperados": apartados_esperados,
        "apartados_esperados_recuperados": sorted(encontrados.intersection(apartados_esperados)),
        "al_menos_un_apartado_esperado": any(a in encontrados for a in apartados_esperados),
    }


def comparar_k(tres: dict[str, Any], seis: dict[str, Any]) -> dict[str, Any]:
    """Compara conjuntos de IDs sin atribuirles relevancia que no haya sido evaluada."""
    if tres["pregunta"] != seis["pregunta"]:
        raise ValueError("Para comparar k ambas preguntas deben ser idénticas")
    ids_tres = {r["id_chunk"] for r in tres["resultados"] if r["id_chunk"]}
    ids_seis = {r["id_chunk"] for r in seis["resultados"] if r["id_chunk"]}
    return {
        "pregunta": tres["pregunta"],
        "k_primero": tres["k"],
        "k_segundo": seis["k"],
        "coincidencias_ids": len(ids_tres & ids_seis),
        "ids_adicionales_segundo": len(ids_seis - ids_tres),
        "latencia_primero_ms": tres["latencia_busqueda_ms"],
        "latencia_segundo_ms": seis["latencia_busqueda_ms"],
    }


def mostrar_consulta(res: dict[str, Any]) -> None:
    print(f"\nPregunta: {res['pregunta']}")
    print(f"k={res['k']} | recuperados={res['recuperados']} | latencia de búsqueda={res['latencia_busqueda_ms']:.2f} ms")
    for r in res["resultados"]:
        print(
            f"  [{r['posicion']}] distancia={r['distancia']:.5f} | "
            f"apartado={r['apartado']} | tipo={r['tipo_contenido']} | "
            f"pág. PDF={r['pagina_pdf_inicio']} | pág. norma={r['pagina_norma_inicio']}"
        )
        print(f"      ID: {r['id_chunk'] or '(no disponible)'}")
        if "vista_previa_local" in r:
            print(f"      Vista previa: {r['vista_previa_local']}")
    if "diagnostico_apartados" in res:
        d = res["diagnostico_apartados"]
        print(
            f"  Apartado esperado encontrado: {d['al_menos_un_apartado_esperado']} "
            f"(esperados: {', '.join(d['apartados_esperados'])})"
        )


def guardar_reporte(salida: Path, contenido: dict[str, Any]) -> None:
    salida.parent.mkdir(parents=True, exist_ok=True)
    # No se persiste el texto de la norma, aunque --mostrar-texto esté activo.
    limpio = json.loads(json.dumps(contenido, ensure_ascii=False))
    for consulta in limpio["consultas"]:
        for resultado in consulta["resultados"]:
            resultado.pop("vista_previa_local", None)
    salida.write_text(json.dumps(limpio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Recuperación semántica del RAG ISO 14067 (sin generación con LLM)")
    parser.add_argument("--vectorstore", type=Path, default=VECTORSTORE_DEFAULT)
    parser.add_argument("--pregunta", action="append", help="Pregunta personal; se puede repetir la opción")
    parser.add_argument("--k", type=int, default=3, help="Chunks a recuperar (predeterminado: 3)")
    parser.add_argument("--comparar", action="store_true", help="Consultar cada pregunta con k=3 y k=6")
    parser.add_argument("--mostrar-texto", action="store_true", help="Imprime una vista previa de cada chunk solo en pantalla")
    parser.add_argument("--guardar", action="store_true", help="Guarda resultados sin texto normativo en JSON local")
    parser.add_argument("--salida", type=Path, default=REPORTE_DEFAULT)
    args = parser.parse_args()

    if args.k < 1:
        parser.error("--k debe ser mayor que cero")
    if args.comparar and args.k != 3:
        parser.error("Con --comparar no indiques --k: se usan automáticamente k=3 y k=6")

    casos = (
        [{"pregunta": p, "apartados_esperados": []} for p in args.pregunta]
        if args.pregunta else CASOS_PRUEBA
    )
    try:
        vs = cargar_indice(args.vectorstore.resolve())
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    informe: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "vectorstore": str(args.vectorstore.resolve()),
        "modelo_embeddings": "models/gemini-embedding-001",
        "consultas": [],
        "comparaciones": [],
        "nota": "Distancias de Chroma; no equivalen a precisión. Los embeddings de las consultas consumen API.",
    }
    try:
        for caso in casos:
            pregunta = caso["pregunta"]
            valores_k = (3, 6) if args.comparar else (args.k,)
            pareja = []
            for k in valores_k:
                r = consultar(vs, pregunta, k=k, mostrar_texto=args.mostrar_texto)
                if caso["apartados_esperados"]:
                    r["diagnostico_apartados"] = evaluar_apartados(r, caso["apartados_esperados"])
                mostrar_consulta(r)
                informe["consultas"].append(r)
                pareja.append(r)
            if args.comparar:
                comparacion = comparar_k(pareja[0], pareja[1])
                informe["comparaciones"].append(comparacion)
                print(f"  Comparación k=3/6: {comparacion['coincidencias_ids']} IDs comunes; "
                      f"{comparacion['ids_adicionales_segundo']} adicionales con k=6")
    except Exception as exc:
        print(f"Error durante la recuperación: {type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc

    if args.guardar:
        guardar_reporte(args.salida.resolve(), informe)
        print(f"\nReporte de recuperación guardado (sin texto normativo): {args.salida.resolve()}")
    print("\nRecuperación finalizada. No se invocó el modelo generativo ni se modificó Chroma.")


if __name__ == "__main__":
    main()
