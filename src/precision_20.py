# Counter cuenta cuántas veces aparece cada token.
from collections import Counter

# Path permite construir rutas y crear carpetas.
from pathlib import Path

# json permite leer y guardar los resultados.
import json

# Importamos las funciones del proyecto.
# Ejecuta este archivo desde la raíz con: python -m src.precision
from src.pipeline_limpieza import procesar_texto
from src.cliente import consultar_modelo


# CONFIGURACIÓN

# Este archivo está en src; su carpeta superior es la raíz del proyecto.
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_DOCS = RAIZ_PROYECTO / "docs"

# Usamos un archivo distinto al ensayo anterior de respuestas largas.
ARCHIVO_RESULTADOS = (
    CARPETA_DOCS / "resultados_metricas_hcp_breve.json"
)

MAX_PALABRAS = 30

# La instrucción solicita brevedad, pero el modelo puede incumplirla.
# Más adelante registramos el número de palabras para comprobarlo.
INSTRUCCION = (
    "Actúa como un copiloto de huella de carbono de producto "
    "que orienta a una persona de empresa que está aprendiendo. "
    f"Responde en español con un máximo de {MAX_PALABRAS} palabras "
    "y una o dos oraciones. "
    "Incluye únicamente la información esencial para responder. "
    "No repitas la pregunta ni añadas introducciones, ejemplos, "
    "listas o recomendaciones adicionales. "
    "No inventes datos ni fuentes. "
    "Si falta información indispensable, indícalo brevemente."
)


# CASOS DE EVALUACIÓN

# Cada tupla contiene:
# 1. Identificador.
# 2. Pregunta que recibirá el modelo.
# 3. Respuesta de referencia usada para calcular las métricas.
#
# Revisa técnicamente estas referencias antes del ensayo.
# No se envían al modelo: se utilizan después para evaluar su respuesta.
CASOS = [
    (
        "HCP01",
        "¿Qué representa la huella de carbono de un producto?",
        "Representa las emisiones y remociones de gases de efecto "
        "invernadero del sistema de producto estudiado, expresadas "
        "en dióxido de carbono equivalente.",
    ),
    (
        "HCP02",
        "¿Para qué debo definir el objetivo de un estudio de HCP?",
        "Para establecer el propósito del estudio, su uso previsto "
        "y los destinatarios de los resultados.",
    ),
    (
        "HCP03",
        "¿Qué debo describir del producto antes de recopilar datos?",
        "Debes describir el producto, su función, sus características "
        "relevantes y los procesos necesarios para proporcionarlo.",
    ),
    (
        "HCP04",
        "¿Qué expresa la unidad funcional?",
        "Expresa de forma cuantificada la función del sistema de "
        "producto y sirve como referencia para relacionar entradas, "
        "salidas y resultados.",
    ),
    (
        "HCP05",
        "¿Qué establecen los límites del sistema?",
        "Establecen los procesos incluidos y excluidos del sistema "
        "de producto y delimitan la recopilación de datos.",
    ),
    (
        "HCP06",
        "¿Qué abarca un estudio de la cuna a la puerta?",
        "Abarca desde la extracción de materias primas hasta la "
        "salida del producto por la puerta definida, especificando "
        "los procesos y transportes incluidos.",
    ),
    (
        "HCP07",
        "¿Por qué conviene dibujar un diagrama de procesos?",
        "Ayuda a identificar etapas, entradas, salidas y conexiones "
        "del sistema, y a organizar los datos que se deben recopilar.",
    ),
    (
        "HCP08",
        "¿Qué son los datos de actividad?",
        "Son cantidades que describen actividades o flujos del "
        "sistema, como consumos de electricidad, combustibles y "
        "materiales, transporte o generación de residuos.",
    ),
    (
        "HCP09",
        "¿Qué es un factor de emisión?",
        "Es un coeficiente que relaciona una actividad o flujo "
        "con emisiones de gases de efecto invernadero, bajo "
        "condiciones y unidades determinadas.",
    ),
    (
        "HCP10",
        "¿Cómo calculo las emisiones de una actividad si tengo "
        "un factor de emisión compatible?",
        "Multiplica el dato de actividad por el factor de emisión, "
        "comprobando la compatibilidad de unidades, el alcance "
        "del factor y su representatividad.",
    ),
    (
        "HCP11",
        "¿Qué debo registrar al recopilar consumos de electricidad?",
        "Registra consumo, unidad, período, instalación o proceso "
        "y fuente documental, indicando su relación con el "
        "producto estudiado.",
    ),
    (
        "HCP12",
        "¿Qué información debo recopilar sobre los combustibles?",
        "Registra el tipo de combustible, cantidad, unidad, "
        "período, uso o proceso asociado y fuente documental.",
    ),
    (
        "HCP13",
        "¿Qué información necesito sobre las materias primas?",
        "Identifica materiales, cantidades, unidades, período y "
        "proveedores, junto con su relación con la producción "
        "del producto estudiado.",
    ),
    (
        "HCP14",
        "¿Qué datos conviene recopilar para evaluar el transporte?",
        "Recopila masa transportada, distancia, modo de transporte "
        "y características relevantes del servicio, según el "
        "método y factor que utilizarás.",
    ),
    (
        "HCP15",
        "¿Qué información necesito sobre los residuos?",
        "Identifica tipo de residuo, cantidad, unidad, tratamiento "
        "o destino, período, evidencia disponible y proceso "
        "que lo genera.",
    ),
    (
        "HCP16",
        "¿Puedo asignar todo el consumo de una fábrica a un producto "
        "si también fabrica otros productos?",
        "No automáticamente. Identifica consumos específicos y "
        "analiza cómo tratar los compartidos, justificando "
        "el procedimiento aplicado.",
    ),
    (
        "HCP17",
        "¿Qué debo hacer si falta un dato de actividad?",
        "Registra el dato faltante y busca información verificable. "
        "Si necesitas estimarlo, documenta el método, los "
        "supuestos y sus limitaciones.",
    ),
    (
        "HCP18",
        "¿Por qué deben coincidir los períodos de consumo "
        "y producción?",
        "Relacionar consumos y producción de períodos distintos "
        "puede distorsionar el resultado por unidad de producto. "
        "Las diferencias deben revisarse y justificarse.",
    ),
    (
        "HCP19",
        "¿Para qué sirven las facturas y registros usados "
        "en el estudio?",
        "Permiten rastrear el origen de los datos, revisar "
        "los cálculos y facilitar la comprobación del estudio.",
    ),
    (
        "HCP20",
        "¿Puedes calcular la HCP exacta de mi producto "
        "si solo te digo su nombre?",
        "No. Se requiere definir el producto y el alcance "
        "y disponer de datos de sus procesos y factores "
        "adecuados.",
    ),
]


# CÁLCULO DE MÉTRICAS

def contar_coincidencias(
    tokens_referencia: list[str],
    tokens_respuesta: list[str],
) -> int:
    """Cuenta los tokens compartidos, considerando sus repeticiones."""

    conteo_referencia = Counter(tokens_referencia)
    conteo_respuesta = Counter(tokens_respuesta)

    # Para cada token compartido, & conserva la menor frecuencia.
    interseccion = conteo_referencia & conteo_respuesta

    return sum(interseccion.values())


def calcular_precision_cobertura_f1(
    tokens_referencia: list[str],
    tokens_respuesta: list[str],
) -> dict[str, float]:
    """Calcula precisión, cobertura y F1 por coincidencias de tokens."""

    # Evitamos divisiones por cero.
    if not tokens_referencia or not tokens_respuesta:
        return {
            "precision": 0.0,
            "cobertura": 0.0,
            "f1": 0.0,
        }

    coincidencias = contar_coincidencias(
        tokens_referencia,
        tokens_respuesta,
    )

    # Proporción de tokens de la respuesta presentes en la referencia.
    precision = coincidencias / len(tokens_respuesta)

    # Proporción de tokens de la referencia presentes en la respuesta.
    cobertura = coincidencias / len(tokens_referencia)

    # F1 combina precisión y cobertura, pero mide similitud léxica:
    # no verifica significado, exactitud ni contradicciones.
    if precision + cobertura == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * cobertura / (precision + cobertura)

    return {
        "precision": precision,
        "cobertura": cobertura,
        "f1": f1,
    }


def calcular_metricas(
    texto_referencia: str,
    texto_respuesta: str,
) -> dict[str, float]:
    """Procesa ambos textos bajo las mismas reglas y los compara."""

    tokens_referencia = procesar_texto(texto_referencia)
    tokens_respuesta = procesar_texto(texto_respuesta)

    return calcular_precision_cobertura_f1(
        tokens_referencia,
        tokens_respuesta,
    )


def resumir_metricas(resultados: list[dict]) -> dict[str, float]:
    """Calcula los promedios, dando el mismo peso a cada caso."""

    if not resultados:
        return {
            "precision_promedio": 0.0,
            "cobertura_promedio": 0.0,
            "f1_promedio": 0.0,
        }

    n = len(resultados)

    return {
        "precision_promedio": sum(
            r["precision"] for r in resultados
        ) / n,
        "cobertura_promedio": sum(
            r["cobertura"] for r in resultados
        ) / n,
        "f1_promedio": sum(
            r["f1"] for r in resultados
        ) / n,
    }


# LECTURA Y GUARDADO

def cargar_resultados() -> list[dict]:
    """Recupera el avance de una ejecución anterior."""

    if not ARCHIVO_RESULTADOS.exists():
        return []

    with ARCHIVO_RESULTADOS.open(
        "r", encoding="utf-8"
    ) as archivo:
        resultados = json.load(archivo)

    if not isinstance(resultados, list):
        raise ValueError(
            "El archivo de resultados debe contener una lista."
        )

    # Evitamos mezclar resultados obtenidos con preguntas,
    # referencias o instrucciones diferentes.
    casos_actuales = {
        identificador: (consulta, referencia)
        for identificador, consulta, referencia in CASOS
    }

    ids_encontrados = set()

    for resultado in resultados:
        identificador = resultado["id"]

        if identificador in ids_encontrados:
            raise ValueError(
                f"Identificador repetido: {identificador}."
            )

        ids_encontrados.add(identificador)

        if identificador not in casos_actuales:
            raise ValueError(
                "El archivo contiene casos de otro experimento. "
                "Usa un nombre de archivo diferente."
            )

        consulta, referencia = casos_actuales[identificador]

        if (
            resultado["consulta"] != consulta
            or resultado["referencia"] != referencia
            or resultado["instruccion"] != INSTRUCCION
        ):
            raise ValueError(
                "Cambió una pregunta, referencia o instrucción. "
                "Usa otro archivo para el nuevo experimento."
            )

    return resultados


def guardar_resultados(resultados: list[dict]) -> None:
    """Guarda el avance sin eliminar las revisiones manuales."""

    CARPETA_DOCS.mkdir(parents=True, exist_ok=True)

    # Primero escribimos un archivo temporal.
    # Si la escritura termina bien, reemplazamos el archivo final.
    temporal = ARCHIVO_RESULTADOS.with_suffix(".tmp")

    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(
            resultados,
            archivo,
            indent=2,
            ensure_ascii=False,
        )

    temporal.replace(ARCHIVO_RESULTADOS)


# SELECCIÓN DE LA MUESTRA MANUAL

def seleccionar_muestra(resultados: list[dict]) -> None:
    """Selecciona cinco F1 bajos y cinco altos sin repetir casos."""

    if len(resultados) < 10:
        raise ValueError(
            "Se necesitan al menos diez resultados para la muestra."
        )

    # Orden ascendente por F1.
    # En caso de empate, usamos el identificador.
    ordenados = sorted(
        resultados,
        key=lambda r: (r["f1"], r["id"]),
    )

    bajos = {r["id"] for r in ordenados[:5]}
    altos = {r["id"] for r in ordenados[-5:]}

    for resultado in resultados:
        if resultado["id"] in bajos:
            grupo = "cinco_f1_mas_bajos"
        elif resultado["id"] in altos:
            grupo = "cinco_f1_mas_altos"
        else:
            grupo = None

        resultado["grupo_revision"] = grupo

        if grupo is not None:
            # setdefault agrega estos campos solo si no existen.
            # Así no reemplazamos una revisión que ya completaste.
            # None aparece como null en el archivo JSON.
            resultado.setdefault(
                "revision_manual",
                {
                    "correccion_factual": None,
                    "completitud": None,
                    "contradiccion": None,
                    "justificacion": "",
                },
            )


# EJECUCIÓN DEL ENSAYO

def main() -> None:
    # Recuperamos las respuestas existentes para no repetir consultas.
    resultados = cargar_resultados()

    completados = {r["id"] for r in resultados}

    for identificador, consulta, referencia in CASOS:
        if identificador in completados:
            print(f"{identificador}: ya generado.")
            continue

        print(f"\n{identificador}: {consulta}")

        try:
            # Esta llamada consulta al modelo y puede generar costos.
            respuesta = consultar_modelo(
                consulta,
                system_instruction=INSTRUCCION,
            )
        except (RuntimeError, ValueError) as error:
            # Un error de consulta no cuenta como respuesta evaluada.
            # El caso quedará pendiente para la siguiente ejecución.
            print(f"Consulta fallida: {error}")
            continue

        # No evaluamos respuestas vacías o no textuales.
        if not isinstance(respuesta, str) or not respuesta.strip():
            print("Respuesta vacía o no textual. Caso pendiente.")
            continue

        metricas = calcular_metricas(referencia, respuesta)

        # Contamos palabras separadas por espacios.
        # Este conteo no equivale a los tokens del proveedor
        # ni a los tokens que produce procesar_texto().
        palabras_respuesta = len(respuesta.split())
        cumple_extension = palabras_respuesta <= MAX_PALABRAS

        # Conservamos la respuesta completa, incluso si supera el límite.
        # Recortarla cambiaría el texto que estamos evaluando.
        resultados.append({
            "id": identificador,
            "consulta": consulta,
            "referencia": referencia,
            "instruccion": INSTRUCCION,
            "respuesta": respuesta,
            "palabras_respuesta": palabras_respuesta,
            "cumple_extension": cumple_extension,
            **metricas,
        })

        completados.add(identificador)

        # Guardamos después de cada caso para conservar el avance.
        guardar_resultados(resultados)

        print("Respuesta:", respuesta)
        print("Palabras:", palabras_respuesta)
        print("Cumple extensión:", cumple_extension)
        print("Métricas:", metricas)

    print(
        f"\nRespuestas evaluadas: {len(resultados)}/{len(CASOS)}"
    )

    if len(resultados) < len(CASOS):
        print(
            "Faltan respuestas. Vuelve a ejecutar el programa "
            "para intentar los casos pendientes."
        )
        return

    # Seleccionamos los extremos de F1 cuando termina la generación.
    seleccionar_muestra(resultados)
    guardar_resultados(resultados)

    print("\nPromedios:")
    for nombre, valor in resumir_metricas(resultados).items():
        print(f"{nombre}: {valor:.3f}")

    incumplimientos = sum(
        not r["cumple_extension"] for r in resultados
    )

    print(
        f"\nRespuestas que superan {MAX_PALABRAS} palabras: "
        f"{incumplimientos}"
    )

    print("\nCasos seleccionados para revisión manual:")

    for resultado in sorted(
        resultados,
        key=lambda r: (r["f1"], r["id"]),
    ):
        if resultado["grupo_revision"] is not None:
            print(
                resultado["id"],
                resultado["grupo_revision"],
                f"F1={resultado['f1']:.3f}",
            )

    print(f"\nResultados guardados en: {ARCHIVO_RESULTADOS}")
    print(
        "Completa revision_manual en los diez casos seleccionados "
        "con la rúbrica de la lección."
    )


# Evita ejecutar consultas al importar las funciones desde los tests.
if __name__ == "__main__":
    main()