# Counter cuenta cuántas veces aparece cada token en una lista.
from collections import Counter

# Importamos la función que procesa el texto antes de compararlo.
from pipeline_limpieza import procesar_texto

# Importamos la función que consulta al modelo de IA.
from cliente import consultar_modelo

import json

def contar_coincidencias(
    tokens_referencia: list[str],
    tokens_respuesta: list[str],
) -> int:
    """
    Cuenta los tokens compartidos entre referencia y respuesta,
    considerando cuántas veces aparece cada uno.
    """

    # Creamos un contador para los tokens de la referencia.
    # Ejemplo: ["python", "es", "python"]
    # produce un conteo equivalente a {"python": 2, "es": 1}.
    conteo_referencia = Counter(tokens_referencia)

    # Contamos también las apariciones de los tokens de la respuesta.
    conteo_respuesta = Counter(tokens_respuesta)

    # El operador & obtiene los tokens presentes en ambos contadores.
    # Para cada token, conserva la menor cantidad de apariciones.
    # Si "python" aparece 2 veces en la referencia y 1 en la respuesta,
    # se cuenta como una coincidencia.
    interseccion = conteo_referencia & conteo_respuesta

    # values() obtiene las cantidades de los tokens compartidos.
    # sum() las suma y devuelve el total de coincidencias.
    return sum(interseccion.values())


def calcular_precision_cobertura_f1(
    tokens_referencia: list[str],
    tokens_respuesta: list[str],
) -> dict[str, float]:
    """
    Calcula precisión, cobertura y F1 a partir de coincidencias de tokens.

    Devuelve un diccionario con valores entre 0.0 y 1.0.
    """

    # Obtenemos la cantidad de tokens coincidentes.
    coincidencias = contar_coincidencias(
        tokens_referencia,
        tokens_respuesta,
    )

    # Una lista vacía se evalúa como False.
    # Si alguna lista está vacía, devolvemos cero para las tres métricas.
    # Esto también evita dividir por cero.
    if not tokens_respuesta or not tokens_referencia:
        return {
            "precision": 0.0,
            "cobertura": 0.0,
            "f1": 0.0,
        }

    # Precisión: proporción de tokens de la respuesta que coincide
    # con los tokens de la referencia.
    precision = coincidencias / len(tokens_respuesta)

    # Cobertura: proporción de tokens de la referencia que está
    # presente en la respuesta.
    cobertura = coincidencias / len(tokens_referencia)

    # F1 combina precisión y cobertura de forma rápida y reproducible.
    # En esta implementación mide coincidencias de tokens, pero no evalúa
    # el significado ni la exactitud, e ignora sinónimos y orden de palabras.
    # Depende de la referencia y del procesamiento del texto, por lo que
    # conviene complementarlo con una revisión de la calidad de la respuesta.
    # Si no existen coincidencias, ambas métricas son cero.
    # Asignamos F1 = 0.0 para evitar una división por cero.
    if precision + cobertura == 0:
        f1 = 0.0
    else:
        # F1 es la media armónica de precisión y cobertura.
        # Su valor disminuye cuando alguna de las dos es baja.
        f1 = (
            2 * precision * cobertura
            / (precision + cobertura)
        )

    # Reunimos las tres métricas en un diccionario.
    resultado = {
        "precision": precision,
        "cobertura": cobertura,
        "f1": f1,
    }

    # Entregamos el diccionario a quien llamó a la función.
    return resultado


def calcular_metricas(texto_referencia, texto_respuesta):
    tokens_referencia = procesar_texto(texto_referencia)
    tokens_respuesta = procesar_texto(texto_respuesta)
    
    return calcular_precision_cobertura_f1(
        tokens_referencia, tokens_respuesta
    )

casos = [
    (
        "¿Qué es Python?",
        "Python es un lenguaje de programación interpretado.",
    ),

    ("¿Cuándo se creó Python?", "Python fue creado en 1991."),

    (
        "¿Qué es una lista en Python?",
        "Una lista es una colección ordenada y modificable.",
    ),
]

resultados = []

for consulta, referencia in casos:
    respuesta = consultar_modelo(consulta, system_instruction="Responde en español con una definición breve, en una sola oración de máximo 15 palabras. Sin listas, ejemplos ni introducciones.")
    
    metricas = calcular_metricas(referencia, respuesta)
    
    print("Consulta:", consulta)
    print("Respuesta:", respuesta)
    print("Métricas:", metricas)
    
    resultados.append({
        "consulta": consulta,
        "respuesta": respuesta,
        **metricas,
    })

resultados = sorted(resultados, key=lambda r: r["f1"])

with open(
    "docs/resultados_metricas.json", "w", encoding="utf-8"
) as archivo:
    json.dump(resultados, archivo, indent=2, ensure_ascii=False)

def resumir_metricas(resultados):
    if not resultados:
        return {
            "precision_promedio": 0,
            "cobertura_promedio": 0,
            "f1_promedio": 0,
        }
    n = len(resultados)
    return {
        "precision_promedio": sum(
            r["precision"] for r in resultados
        ) / n,
        "cobertura_promedio": sum(
            r["cobertura"] for r in resultados
        ) / n,
        "f1_promedio": sum(r["f1"] for r in resultados) / n,
    }
    
print("Promedios")
print(resumir_metricas(resultados))
    
peores_casos = sorted(resultados, key=lambda r: r["f1"])

for caso in peores_casos[:3]:
    print(caso["consulta"], caso["f1"])



# Ctrl + K / Crtl + C - shortcur para comentar en bloque
# Ctrl + K / Crtl + U - shortcur para excluir comentario en bloque
# # Aplicamos a la respuesta el mismo procesamiento que a la referencia.
# respuesta = procesar_texto(texto_respuesta)

# # Comparamos ambas listas de tokens y calculamos las métricas.
# resultado = calcular_precision_cobertura_f1(
#     referencia,
#     respuesta,
# )

# # Mostramos el texto original que devolvió el modelo.
# print("Respuesta:", texto_respuesta)

# # len() devuelve la cantidad de tokens de cada lista,
# # incluyendo los tokens repetidos.
# print("Tokens de referencia:", len(referencia))
# print("Tokens de respuesta:", len(respuesta))

# # Mostramos el diccionario con precisión, cobertura y F1.
# print(resultado)