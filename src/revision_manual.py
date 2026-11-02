import json
from pathlib import Path


# Localizamos el archivo generado por precision_20.py.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent

ARCHIVO_RESULTADOS = (
    RAIZ_PROYECTO
    / "docs"
    / "resultados_metricas_hcp_breve.json"
)

CAMPOS_REVISION = (
    "correccion_factual",
    "completitud",
    "contradiccion",
    "justificacion",
)


def cargar_resultados() -> list[dict]:
    """Lee las respuestas y métricas del ensayo."""

    if not ARCHIVO_RESULTADOS.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: {ARCHIVO_RESULTADOS}"
        )

    with ARCHIVO_RESULTADOS.open(
        "r", encoding="utf-8"
    ) as archivo:
        resultados = json.load(archivo)

    # El archivo debe contener una lista de casos.
    if not isinstance(resultados, list):
        raise ValueError(
            "El archivo debe contener una lista de resultados."
        )

    return resultados


def guardar_resultados(resultados: list[dict]) -> None:
    """Guarda el avance conservando los demás datos del ensayo."""

    # Escribimos primero en un archivo temporal para reducir
    # el riesgo de dejar el archivo final incompleto.
    temporal = ARCHIVO_RESULTADOS.with_suffix(".tmp")

    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(
            resultados,
            archivo,
            indent=2,
            ensure_ascii=False,
        )

    # Reemplazamos el archivo original cuando termina la escritura.
    temporal.replace(ARCHIVO_RESULTADOS)


def revision_completa(caso: dict) -> bool:
    """Comprueba si los cuatro campos tienen contenido."""

    revision = caso.get("revision_manual")

    if not isinstance(revision, dict):
        return False

    # No confundimos cero o False con una respuesta pendiente:
    # podrían ser categorías válidas de una rúbrica.
    for campo in CAMPOS_REVISION:
        valor = revision.get(campo)

        if valor is None:
            return False

        if isinstance(valor, str) and not valor.strip():
            return False

    return True


def pedir_valoracion(pregunta: str) -> str:
    """Solicita una respuesta y evita guardar campos vacíos."""

    while True:
        valor = input(pregunta).strip()

        if valor:
            return valor

        print("Ingresa una valoración antes de continuar.")


def revisar_caso(caso: dict) -> dict:
    """Muestra la evidencia y recoge la revisión del usuario."""

    print("\n" + "=" * 60)
    print(f"Caso: {caso['id']}")
    print(f"Grupo: {caso['grupo_revision']}")
    print(f"F1: {caso['f1']:.3f}")

    print("\nPREGUNTA:")
    print(caso["consulta"])

    print("\nREFERENCIA:")
    print(caso["referencia"])

    print("\nRESPUESTA DEL MODELO:")
    print(caso["respuesta"])

    print("\nREVISION MANUAL")
    print("Utiliza las categorías de la rúbrica del curso.")
    print(
        "Distingue los errores de las omisiones: "
        "una omisión no implica una contradicción."
    )

    correccion = pedir_valoracion(
        "\nCorrección factual: "
    )

    completitud = pedir_valoracion(
        "Completitud: "
    )

    contradiccion = pedir_valoracion(
        "Contradicción: "
    )

    justificacion = pedir_valoracion(
        "Justificación (qué es correcto, qué falta "
        "y qué contradicción observas, si existe): "
    )

    # Devolvemos la revisión sin modificar la respuesta del modelo.
    return {
        "correccion_factual": correccion,
        "completitud": completitud,
        "contradiccion": contradiccion,
        "justificacion": justificacion,
    }


def main() -> None:
    resultados = cargar_resultados()

    # Recuperamos únicamente los casos seleccionados
    # por precision_20.py para revisión manual.
    muestra = [
        caso
        for caso in resultados
        if caso.get("grupo_revision") in (
            "cinco_f1_mas_bajos",
            "cinco_f1_mas_altos",
        )
    ]

    # Comprobamos que estén los dos grupos esperados.
    bajos = sum(
        caso["grupo_revision"] == "cinco_f1_mas_bajos"
        for caso in muestra
    )
    altos = sum(
        caso["grupo_revision"] == "cinco_f1_mas_altos"
        for caso in muestra
    )

    if bajos != 5 or altos != 5:
        raise ValueError(
            "La muestra debe contener cinco casos con menor F1 "
            "y cinco con mayor F1. Completa primero precision_20.py."
        )

    # Revisamos los casos de menor a mayor F1.
    muestra = sorted(
        muestra,
        key=lambda caso: (caso["f1"], caso["id"]),
    )

    print("Revisión manual de diez respuestas del copiloto HCP.")
    print("Las calificaciones se guardarán como texto.")
    print("Puedes interrumpir con Ctrl + C.")
    print("Se conserva cada caso cuya revisión ya fue guardada.")

    try:
        for caso in muestra:
            # No repetimos revisiones completadas anteriormente.
            if revision_completa(caso):
                print(f"\n{caso['id']}: revisión ya completada.")
                continue

            # Solo asignamos la revisión cuando se hayan
            # respondido sus cuatro campos.
            caso["revision_manual"] = revisar_caso(caso)

            # Guardamos después de cada caso completo.
            guardar_resultados(resultados)

            print(f"{caso['id']}: revisión guardada.")

    except (KeyboardInterrupt, EOFError):
        # La revisión del caso en curso no se guarda si está
        # incompleta. Los casos anteriores permanecen guardados.
        print(
            "\nRevisión interrumpida. "
            "Las revisiones guardadas se conservan."
        )

    completadas = sum(
        revision_completa(caso) for caso in muestra
    )

    print(f"\nRevisiones completadas: {completadas}/10")

    if completadas == 10:
        print(
            "La muestra está revisada. "
            "Ya puedes redactar docs/limites_metrica.md "
            "a partir de tus observaciones."
        )
    else:
        print(
            "Vuelve a ejecutar el programa "
            "para continuar con los casos pendientes."
        )


# Importar este módulo no inicia la revisión.
if __name__ == "__main__":
    main()