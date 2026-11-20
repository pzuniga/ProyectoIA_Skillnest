"""Lee los registros JSONL del Bloque 28 sin realizar llamadas a Gemini.

Desde la raíz del proyecto:
    python -m src.leer_registros_proyecto
    python -m src.leer_registros_proyecto --archivo registros_latencia_costo.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ARCHIVO_DEFAULT = Path(__file__).resolve().parent.parent / "registros_latencia_costo.jsonl"


def leer_registros(ruta: Path) -> list[dict]:
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el registro: {ruta}")
    registros = []
    with ruta.open(encoding="utf-8") as f:
        for nro, linea in enumerate(f, 1):
            if not linea.strip():
                continue
            try:
                registro = json.loads(linea)
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSONL inválido en línea {nro}") from exc
            if not isinstance(registro, dict) or not all(
                c in registro for c in ("timestamp", "pregunta", "k", "tiempos_ms", "tiempo_total_ms", "tokens")
            ):
                raise ValueError(f"Registro incompleto en línea {nro}")
            registros.append(registro)
    return registros


def main() -> None:
    parser = argparse.ArgumentParser(description="Leer evidencia JSONL del Bloque 28")
    parser.add_argument("--archivo", type=Path, default=ARCHIVO_DEFAULT)
    args = parser.parse_args()
    try:
        registros = leer_registros(args.archivo)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Consultas registradas: {len(registros)}")
    for r in registros:
        tokens = r["tokens"] or {}
        tiempos = r["tiempos_ms"]
        print(
            f"k={r['k']} | in={tokens.get('input_tokens')} | out={tokens.get('output_tokens')} | "
            f"recup={tiempos.get('embed_y_busqueda')} ms | prompt={tiempos.get('armado_prompt')} ms | "
            f"gen={tiempos.get('generacion')} ms | total={r['tiempo_total_ms']} ms | "
            f"USD estimado={r.get('costo_estimado_usd')} | {r['pregunta'][:70]}"
        )


if __name__ == "__main__":
    main()
