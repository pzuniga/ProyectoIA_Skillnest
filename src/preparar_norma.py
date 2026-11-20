"""Preparación local de corpus normativos PDF para el RAG del curso Skillnest.

Objetivo: extraer texto de un PDF digital, reconocer apartados mediante su
numeración y tipografía y devolver documentos LangChain con metadatos de origen.

No usa modelos, no genera embeddings y no modifica rag_indexer.py.
No reproduce ni publica automáticamente el corpus protegido.

Dependencias: pip install pymupdf
Integración posterior: langchain-core (instalado junto con LangChain del curso).

Este ejemplo incluye una configuración para el ejemplar NCh-ISO 14067:2019
inspeccionado. Para otra norma deben validarse los recortes y las reglas.
"""
from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
import json
import re
import unicodedata
from collections import Counter
from typing import Any
from datetime import datetime, timezone
import os
import tempfile

import pymupdf as fitz  # PyMuPDF (API actual; alias compatible con funciones existentes)


# Rutas del proyecto en Windows:
# C:\ProyectoIA_Skillnest\src\preparar_norma.py
# C:\ProyectoIA_Skillnest\docs\Biblioteca\NCh-ISO 14067_2019.pdf
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIBLIOTECA = PROJECT_ROOT / "docs" / "Biblioteca"
RUTA_NORMA = BIBLIOTECA / "NCh-ISO 14067_2019.pdf"
RUTA_REPORTE = PROJECT_ROOT / "diagnostico_corpus_iso14067.json"
RUTA_CORPUS = PROJECT_ROOT / "data" / "corpus" / "nch_iso_14067_2019.json"
VERSION_ESQUEMA_CORPUS = "1.0"


# Coincide con títulos como 6, 6.3.4.3, 6.4.9.4.4, A.1, E.2.1.
# La forma tipográfica y la posición se verifican por separado.
PATRON_APARTADO = re.compile(
    r"^(?P<id>(?:[1-8](?:\.\d+){0,5}|[A-E](?:\.\d+){1,5}))\.?\s*(?P<titulo>.*)$"
)
PATRON_ANEXO = re.compile(r"^Anexo\s+([A-E])$", re.IGNORECASE)
PATRON_CONTAMINACION = re.compile(
    r"USO EXCLUSIVO|Copia para uso exclusivo|Impreso por:|©\s*(?:ISO|INN)", re.I
)
PATRON_ROTULO_VISUAL = re.compile(r"^(?P<tipo>Tabla|Figura)\s+(?P<numero>\d+)\s*[–—-]\s*(?P<titulo>.*)$", re.I | re.S)
PATRON_MARCADOR = re.compile(r"^(?:NOTA(?:\s+\d+)?|EJEMPLO(?:\s+\d+)?|[a-z]\)|[—–•])(?:\s|$)", re.I)


@dataclass(frozen=True)
class RegionEspecial:
    pagina_pdf: int
    y_inicio: float
    y_fin: float
    tipo: str
    referencia: str
    motivo: str


@dataclass(frozen=True)
class ConfigNorma:
    documento: str
    pagina_inicio: int  # 1-based e inclusiva
    pagina_fin: int     # 1-based e inclusiva
    desfase_pagina_norma: int = 12
    margen_superior: float = 80.0
    margen_inferior: float = 776.0
    margen_izquierdo: float = 35.0
    margen_derecho: float = 559.0
    regiones_especiales: tuple[RegionEspecial, ...] = ()


CONFIG_NCH_ISO_14067 = ConfigNorma(
    documento="NCh-ISO 14067:2019",
    pagina_inicio=13,
    pagina_fin=65,
    desfase_pagina_norma=12,
    # Las tablas/figuras complejas no se convierten a prosa de forma automática:
    # sus relaciones semánticas deben validarse por separado antes de indexarlas.
    regiones_especiales=(
        RegionEspecial(10, 120, 545, "figura", "Figura 1",
                       "Diagrama de relación entre normas de la familia ISO 14060"),
        RegionEspecial(12, 135, 360, "figura", "Figura 2",
                       "Diagrama de relación entre ISO 14067 y otras normas"),
        RegionEspecial(44, 171, 588, "tabla", "Tabla 1",
                       "Cabeceras combinadas y cruces de columnas: revisión manual"),
        RegionEspecial(45, 80, 695, "figura", "Figura 3",
                       "Diagrama espacial con leyenda: revisión manual"),
    ),
)


@dataclass
class Linea:
    pagina_pdf: int
    y: float
    x: float
    texto: str
    negrita: bool
    tamano: float


@dataclass
class Unidad:
    apartado: str
    titulo: str
    documento: str
    pagina_pdf_inicio: int
    pagina_pdf_fin: int
    caracter: str
    tipo_contenido: str = "apartado"
    lineas: list[Linea] = field(default_factory=list)

    @property
    def apartado_padre(self) -> str:
        if self.apartado.startswith("Anexo "):
            return ""
        if self.apartado[:1] in "ABCDE" and "." not in self.apartado:
            return ""
        if "." in self.apartado:
            parent = self.apartado.rsplit(".", 1)[0]
            if len(parent) == 1 and parent in "ABCDE":
                return f"Anexo {parent}"
            return parent
        return ""

    @property
    def texto(self) -> str:
        return reconstruir_parrafos(self.lineas)

    def metadatos(self, config: ConfigNorma) -> dict[str, str | int]:
        return {
            "fuente": self.documento,  # Compatible con formatear_contexto de la profesora
            "documento": self.documento,
            "apartado": self.apartado,
            "apartado_padre": self.apartado_padre,
            "titulo": self.titulo,
            "caracter": self.caracter,
            "tipo_contenido": self.tipo_contenido,
            "pagina_pdf_inicio": self.pagina_pdf_inicio,
            "pagina_pdf_fin": self.pagina_pdf_fin,
            "pagina_norma_inicio": self.pagina_pdf_inicio - config.desfase_pagina_norma,
            "pagina_norma_fin": self.pagina_pdf_fin - config.desfase_pagina_norma,
        }


# Lectura de las tres figuras realizada directamente desde los diagramas del PDF.
# Son paráfrasis breves para recuperación, no sustituyen al original.
# Cada elemento queda pendiente de aprobación por el usuario antes de indexar.
DESCRIPCIONES_NCH_ISO_14067 = {
    "Figura 1": (
        "Relaciones mostradas: ISO 14064-1 -> inventario e informe de GEI "
        "organizacionales; ISO 14064-2 -> documentación e informes de proyectos "
        "de GEI; ISO 14067 -> informe de estudio de huella de carbono de producto "
        "(HCP por unidad funcional o HCP parcial por unidad declarada). "
        "Las tres rutas conducen a declaraciones de GEI. La figura relaciona "
        "ISO 14064-3 con la validación o verificación, ISO 14065 con los "
        "organismos de validación y verificación e ISO 14066 con las competencias "
        "de sus equipos. También representa los requisitos de los programas de "
        "GEI o de los usuarios previstos."
    ),
    "Figura 2": (
        "Relaciones mostradas: ISO 14044 (requisitos de ACV) e ISO/TS 14027 "
        "(establecimiento de RCP) se conectan con ISO 14067, que conduce al "
        "informe del estudio de HCP. Desde ese informe se distingue la "
        "comunicación de huella, vinculada con ISO 14026, ISO 14044 e "
        "ISO/TS 14071, del uso interno del informe para apoyar decisiones, "
        "sin comunicación de huella."
    ),
    "Figura 3": (
        "Diagrama ilustrativo de componentes de HCP y HCP parcial, en kg CO2e "
        "respecto de un eje cero. Componentes numerados: 1, otras emisiones de GEI; "
        "2, emisiones de aeronaves; 3, emisiones biogénicas; 4, emisiones por "
        "cambio directo de uso del suelo (CUSd) y cambio en la gestión del suelo; "
        "5, emisiones del uso del suelo distintas del cambio en la gestión; "
        "6, emisiones y remociones fósiles netas; 7, remociones biogénicas; "
        "8, remociones por CUSd y cambio en la gestión del suelo; "
        "9, remociones del uso del suelo distintas del cambio en la gestión; "
        "10, carbono biogénico en el producto; 11, emisiones por cambio indirecto "
        "de uso del suelo (CUSi); 12, remociones por CUSi. "
        "Las tramas distinguen componentes que se deberían incluir, contenido "
        "que se documenta separadamente si se calcula y no se suma a la HCP "
        "(componente 10), y componentes considerados por separado (11 y 12). "
        "La figura indica que las emisiones y remociones fósiles, CUSd y CUSi "
        "pueden contribuir positiva o negativamente. Es ilustrativa y no "
        "sustituye los apartados 6.4.9.2 a 6.4.9.7."
    ),
}


@dataclass
class ElementoVisual:
    tipo: str                 # "tabla" o "figura"
    documento: str
    referencia: str           # p.ej. "Tabla 1"
    titulo: str
    pagina_pdf: int
    pagina_norma: str
    apartado: str
    caracter: str
    descripcion: str
    texto_extraido: str
    filas: list[dict[str, Any]] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)
    aprobado: bool = False

    @property
    def id(self) -> str:
        return self.referencia.lower().replace(" ", "_")

    @property
    def huella_sha256(self) -> str:
        # Si cambia la extracción o descripción, se invalidan aprobaciones previas.
        datos = {"tipo": self.tipo, "referencia": self.referencia,
                 "titulo": self.titulo, "documento": self.documento,
                 "pagina": self.pagina_pdf,
                 "apartado": self.apartado, "descripcion": self.descripcion,
                 "texto": self.texto_extraido, "filas": self.filas,
                 "notas": self.notas}
        serial = json.dumps(datos, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(serial.encode("utf-8")).hexdigest()

    def metadatos(self, tipo_contenido: str) -> dict[str, str | int | bool]:
        return {
            "fuente": self.documento,
            "apartado": self.apartado,
            "titulo": self.titulo,
            "referencia_visual": self.referencia,
            "tipo_contenido": tipo_contenido,
            "caracter": self.caracter,
            "pagina_pdf_inicio": self.pagina_pdf,
            "pagina_pdf_fin": self.pagina_pdf,
            "pagina_norma": self.pagina_norma,
            "validacion_humana": self.aprobado,
        }

    def registros_corpus(self) -> list[dict[str, Any]]:
        """Registros serializables fieles al contenido que se usará en LangChain.

        No indexamos texto_extraido de figuras porque el orden de lectura
        geométrico puede mezclar leyendas y cifras.
        """
        if self.tipo == "figura":
            contenido = f"{self.referencia}. {self.titulo}\n{self.descripcion}"
            return [{"page_content": contenido, "metadata": self.metadatos("figura")}]
        registros = []
        if self.descripcion:
            registros.append({
                "page_content": (f"{self.referencia}. {self.titulo}\n"
                                 f"{self.descripcion}\n"
                                 f"Notas: {' '.join(self.notas)}"),
                "metadata": self.metadatos("tabla_resumen"),
            })
        for i, fila in enumerate(self.filas, start=1):
            cols = "; ".join(fila.get("columnas_marcadas", []))
            contenido = (f"{self.referencia}, fila {i}, apartado {fila.get('apartado', '')}. "
                         f"{fila.get('concepto', '')}. "
                         f"Columnas marcadas con X: {cols}. "
                         "La ausencia de X en otra columna no debe interpretarse "
                         "automáticamente como una prohibición. "
                         f"Nota de tabla: {' '.join(self.notas)}")
            meta = self.metadatos("tabla_fila")
            meta["fila_tabla"] = i
            meta["apartado_fila"] = str(fila.get("apartado", ""))
            registros.append({"page_content": contenido, "metadata": meta})
        return registros

    def documentos_langchain(self):
        from langchain_core.documents import Document
        return [Document(page_content=r["page_content"], metadata=r["metadata"])
                for r in self.registros_corpus()]


@dataclass
class Resultado:
    config: ConfigNorma
    unidades: list[Unidad]
    regiones_especiales: list[RegionEspecial]
    estadisticas: dict[str, Any]
    alertas: list[str]
    elementos_visuales: list[ElementoVisual] = field(default_factory=list)
    rotulos_detectados: list[dict[str, Any]] = field(default_factory=list)

    def aprobar_visuales(self, aprobaciones: dict[str, Any]) -> list[str]:
        """Aplica revisiones humanas solo si coincide la huella del contenido."""
        errores = []
        for e in self.elementos_visuales:
            revision = aprobaciones.get(e.id, {})
            if not revision.get("aprobado", False):
                continue
            if e.errores:
                errores.append(f"{e.referencia}: existen errores de extracción")
            elif revision.get("sha256") != e.huella_sha256:
                errores.append(f"{e.referencia}: revisión desactualizada (huella no coincide)")
            else:
                e.aprobado = True
        return errores

    def registros_corpus(self, incluir_contenedores: bool = False,
                        incluir_visuales: bool = True,
                        solo_visuales_aprobados: bool = True) -> list[dict[str, Any]]:
        """Representación serializable de los mismos Document del RAG.

        Los elementos visuales solo entran si fueron aprobados con SHA-256
        coincidente en esta ejecución; no utiliza contenido de NotebookLM.
        """
        registros = []
        for unidad in self.unidades:
            cuerpo = unidad.texto.strip()
            if not cuerpo and not incluir_contenedores:
                continue
            contenido = f"{unidad.apartado}. {unidad.titulo}\n{cuerpo}".strip()
            registros.append({"page_content": contenido,
                              "metadata": unidad.metadatos(self.config)})
        if incluir_visuales:
            for elemento in self.elementos_visuales:
                if solo_visuales_aprobados and not elemento.aprobado:
                    continue
                registros.extend(elemento.registros_corpus())
        return registros

    def documentos_langchain(self, incluir_contenedores: bool = False,
                             incluir_visuales: bool = True,
                             solo_visuales_aprobados: bool = True):
        """Entrega List[Document] para indexar_corpus(..., es_documento=True)."""
        try:
            from langchain_core.documents import Document
        except ImportError as exc:
            raise RuntimeError("Falta langchain-core; instale las dependencias del curso") from exc
        return [Document(page_content=r["page_content"], metadata=r["metadata"])
                for r in self.registros_corpus(incluir_contenedores,
                                               incluir_visuales,
                                               solo_visuales_aprobados)]


def normalizar_texto(texto: str) -> str:
    # Algunos PDF insertan un espacio tras la ligadura (ej. 'cuantiﬁ cación').
    # Se repara la ligadura antes de NFKC, sin reescribir frases o requisitos.
    texto = re.sub(r"([ﬁﬂ])\s+(?=[a-záéíóúñ])", r"\1", texto)
    texto = unicodedata.normalize("NFKC", texto)
    texto = re.sub(r"[\t\u00a0]+", " ", texto)
    texto = re.sub(r" {2,}", " ", texto)
    return texto.strip()


def _dentro_region(page: int, y: float, config: ConfigNorma) -> bool:
    return any(r.pagina_pdf == page and r.y_inicio <= y <= r.y_fin
               for r in config.regiones_especiales)


def _extraer_lineas(pagina, numero_pdf: int, config: ConfigNorma) -> tuple[list[Linea], dict]:
    """Reconstrucción geométrica; descarta marcas laterales y pies de página."""
    piezas: list[Linea] = []
    stats = {"lineas_brutas": 0, "lineas_excluidas": 0, "lineas_region_especial": 0,
             "caracteres_brutos_horizontales": 0}
    for bloque in pagina.get_text("dict")["blocks"]:
        if bloque.get("type") != 0:
            continue
        for linea in bloque["lines"]:
            trozos = linea.get("spans", [])
            if not trozos:
                continue
            original = "".join(s["text"] for s in trozos).strip()
            if not original:
                continue
            stats["lineas_brutas"] += 1
            bbox = linea["bbox"]
            horizontal = abs(linea["dir"][0] - 1.0) <= 0.01 and abs(linea["dir"][1]) <= 0.01
            if horizontal:
                stats["caracteres_brutos_horizontales"] += len(original)
            x, y = bbox[0], bbox[1]
            if (not horizontal or y < config.margen_superior or y >= config.margen_inferior
                    or x < config.margen_izquierdo or x > config.margen_derecho
                    or PATRON_CONTAMINACION.search(original)):
                stats["lineas_excluidas"] += 1
                continue
            if _dentro_region(numero_pdf, y, config):
                stats["lineas_region_especial"] += 1
                continue
            # Identifica negrita a través del nombre de la fuente y flags de PyMuPDF.
            negrita = all("bold" in s["font"].lower() or bool(s["flags"] & 16)
                          for s in trozos if s["text"].strip())
            piezas.append(Linea(numero_pdf, y, x, normalizar_texto(original), negrita,
                                max(s["size"] for s in trozos)))

    # PyMuPDF puede separar un marcador/lista y su texto en dos Lineas a la
    # misma altura. Se agrupan, sin mezclar distintas filas de una tabla (las
    # tablas complejas han sido apartadas de la región indexable).
    piezas.sort(key=lambda l: (round(l.y, 1), l.x))
    combinadas: list[Linea] = []
    for l in piezas:
        if combinadas and combinadas[-1].pagina_pdf == l.pagina_pdf and abs(combinadas[-1].y - l.y) < 1.2:
            anterior = combinadas[-1]
            anterior.texto += " " + l.texto
            anterior.negrita = anterior.negrita and l.negrita
            anterior.tamano = max(anterior.tamano, l.tamano)
        else:
            combinadas.append(l)
    return combinadas, stats


def _identificar_encabezado(linea: Linea):
    if not linea.negrita or linea.tamano < 10.5:
        return None
    m = PATRON_ANEXO.fullmatch(linea.texto)
    if m and linea.tamano >= 13:
        return f"Anexo {m.group(1).upper()}", ""
    m = PATRON_APARTADO.match(linea.texto)
    if not m or linea.x > 100:
        return None
    id_ = m.group("id")
    if id_[:1].isdigit() and not id_[0] in "12345678":
        return None
    return id_, m.group("titulo").strip()


def reconstruir_parrafos(lineas: list[Linea]) -> str:
    """Une líneas visuales dentro de párrafos, conserva notas y listas."""
    if not lineas:
        return ""
    fragmentos: list[str] = []
    texto_actual = ""
    anterior: Linea | None = None
    for lin in lineas:
        nueva_estructura = bool(PATRON_MARCADOR.match(lin.texto))
        nueva_pagina = bool(anterior is not None and lin.pagina_pdf != anterior.pagina_pdf)
        salto = anterior is None or nueva_estructura or nueva_pagina
        if anterior is not None and not salto:
            dist = lin.y - anterior.y
            if dist > 19:  # Deja separados párrafos, listas y notas.
                salto = True
        if salto:
            if texto_actual.strip():
                fragmentos.append(texto_actual.strip())
            texto_actual = lin.texto
        else:
            if texto_actual.endswith("-") and lin.texto[:1].islower():
                texto_actual = texto_actual[:-1] + lin.texto
            else:
                texto_actual += " " + lin.texto
        anterior = lin
    if texto_actual.strip():
        fragmentos.append(texto_actual.strip())
    return "\n\n".join(fragmentos)


def _tipo_caracter(apartado: str) -> str:
    if apartado.startswith("Anexo "):
        letra = apartado[-1]
    elif apartado[:1] in "ABCDE" and not apartado[:1].isdigit():
        letra = apartado[0]
    else:
        return "cuerpo_normativo"
    return "anexo_normativo" if letra in "ABC" else "anexo_informativo"


def _texto_de_region(pagina, region: RegionEspecial) -> str:
    """Recoge etiquetas del gráfico por geometría, evitando el ruido lateral."""
    lineas = []
    for bloque in pagina.get_text("dict")["blocks"]:
        if bloque.get("type") != 0:
            continue
        for linea in bloque.get("lines", []):
            x0, y0, x1, y1 = linea["bbox"]
            orientacion = linea.get("dir", (1, 0))
            if abs(orientacion[0] - 1) > 0.01 or abs(orientacion[1]) > 0.01:
                continue
            if y0 < region.y_inicio or y0 > region.y_fin or x0 < 35 or x1 > 560:
                continue
            texto = normalizar_texto("".join(s["text"] for s in linea["spans"]))
            if not texto or PATRON_CONTAMINACION.search(texto):
                continue
            if PATRON_ROTULO_VISUAL.match(texto):
                continue
            lineas.append(Linea(region.pagina_pdf, y0, x0, texto, False, 0))
    lineas.sort(key=lambda lin: (round(lin.y), lin.x))
    return "\n".join(l.texto for l in lineas)


def _inventariar_rotulos(pdf) -> list[dict[str, Any]]:
    """Busca rótulos rotulados Tabla/Figura en TODO el archivo, incluida introducción."""
    resultado = []
    vistos = set()
    for i in range(len(pdf)):
        for bloque in pdf[i].get_text("blocks"):
            texto = normalizar_texto(bloque[4])
            # Captions pueden ocupar dos líneas, pero su comienzo identifica el rótulo.
            mat = PATRON_ROTULO_VISUAL.match(texto)
            if mat:
                ref = f"{mat.group('tipo').capitalize()} {mat.group('numero')}"
                if (ref, i+1) in vistos:
                    continue
                vistos.add((ref, i+1))
                resultado.append({"referencia": ref, "pagina_pdf": i+1,
                                  "titulo": re.sub(r"\s+", " ", mat.group("titulo")).strip(),
                                  "y": round(bloque[1], 1)})
    return resultado


def _procesar_tabla(pagina, region: RegionEspecial, rotulo: dict[str, Any],
                    config: ConfigNorma) -> ElementoVisual:
    e = ElementoVisual(
        tipo="tabla", documento=config.documento, referencia=region.referencia,
        titulo=rotulo.get("titulo", ""), pagina_pdf=region.pagina_pdf,
        pagina_norma=str(region.pagina_pdf-config.desfase_pagina_norma),
        apartado="6.4.9.8" if config.documento == "NCh-ISO 14067:2019"
                                 and region.referencia == "Tabla 1" else "",
        caracter="resumen_informativo" if config.documento == "NCh-ISO 14067:2019"
                                          and region.referencia == "Tabla 1" else "tabla",
        descripcion=("Resumen informativo de requisitos y orientaciones; "
                     "para precisar una obligación deben consultarse los apartados citados."),
        texto_extraido="",
    )
    try:
        # Clip suficiente para la malla tabular, no confundir con texto de alrededor.
        clip = fitz.Rect(42, max(0, region.y_inicio+35), 545, region.y_fin)
        tablas = pagina.find_tables(clip=clip).tables
        candidatos = [t for t in tablas if t.row_count >= 3 and t.col_count >= 2]
        if not candidatos:
            e.errores.append("No se reconoció una tabla con al menos 3 filas y 2 columnas")
            return e
        tabla = max(candidatos, key=lambda t: t.row_count*t.col_count)
        grid = tabla.extract()
        e.texto_extraido = f"Malla detectada: {tabla.row_count} filas, {tabla.col_count} columnas."
        # La Tabla 1 del PDF tiene dos filas de encabezado, 6 filas de datos
        # y una nota al pie. En nuevas normas debe suministrarse otro adaptador.
        if config.documento == "NCh-ISO 14067:2019" and region.referencia == "Tabla 1":
            if tabla.col_count != 7 or tabla.row_count != 9:
                e.errores.append("Dimensión inesperada de Tabla 1; comprobar manualmente")
            encabezados = [normalizar_texto(str(h or "").replace("\n", " ")) for h in grid[1]]
            if not all(encabezados[j] for j in range(2, 7)):
                e.errores.append("Falta algún encabezado de tratamiento/documentación")
            for i, fila in enumerate(grid[2:8]):
                apartado = normalizar_texto(str(fila[0] or ""))
                concepto = normalizar_texto(str(fila[1] or "").replace("\n", " "))
                # La tabla usa 'a' como superíndice de nota al pie.
                # En la extracción queda pegado: CUSda, CUSia, sueloa...
                concepto = re.sub(r"\b(CUSd|CUSi|suelo|productos)a\b", r"\1 (nota a)", concepto)
                marcadas = []
                for j in range(2, 7):
                    valor = normalizar_texto(str(fila[j] or ""))
                    if valor.upper() == "X":
                        marcadas.append(encabezados[j])
                    elif valor:
                        e.errores.append(f"Valor inesperado en fila {i+1}, columna {j+1}: {valor}")
                if not re.fullmatch(r"6\.4\.9\.\d", apartado) or not concepto or not marcadas:
                    e.errores.append(f"Fila {i+1} incompleta o con marcación faltante")
                e.filas.append({"apartado": apartado, "concepto": concepto,
                                "columnas_marcadas": marcadas})
            e.notas = [normalizar_texto(str(grid[-1][0] or "").replace("\n", " "))]
            if not e.notas[0]:
                e.errores.append("No se encontró la nota de Tabla 1")
        else:
            # Fallback conservador reutilizable: guarda filas, sin atribuir
            # semántica a cabeceras combinadas sin adaptador validado.
            e.errores.append("Tabla detectada, pendiente de adaptador y validación de cabeceras")
            e.filas = [{"apartado": "", "concepto": " / ".join(str(c or "") for c in fila),
                        "columnas_marcadas": []} for fila in grid]
    except Exception as exc:
        e.errores.append(f"Falló extracción de tabla: {type(exc).__name__}: {exc}")
    return e


def _procesar_figura(pagina, region: RegionEspecial, rotulo: dict[str, Any],
                     config: ConfigNorma) -> ElementoVisual:
    numeros_preliminares = {10: "x", 12: "xii"} if config.documento == "NCh-ISO 14067:2019" else {}
    n_pagina = numeros_preliminares.get(
        region.pagina_pdf, str(region.pagina_pdf-config.desfase_pagina_norma)
    )
    descripciones = (DESCRIPCIONES_NCH_ISO_14067
                     if config.documento == "NCh-ISO 14067:2019" else {})
    return ElementoVisual(
        tipo="figura", documento=config.documento, referencia=region.referencia,
        titulo=rotulo.get("titulo", ""), pagina_pdf=region.pagina_pdf,
        pagina_norma=n_pagina,
        apartado="Introducción" if region.pagina_pdf < config.pagina_inicio
                 else ("6.4.9.8" if config.documento == "NCh-ISO 14067:2019" else ""),
        caracter="contextual" if region.pagina_pdf < config.pagina_inicio else "ilustracion_informativa",
        descripcion=descripciones.get(region.referencia, ""),
        texto_extraido=_texto_de_region(pagina, region),
        errores=[] if region.referencia in descripciones
                 else ["Figura identificada, pero sin descripción validada para esta norma"],
    )


def _extraer_visuales(pdf, config: ConfigNorma):
    rotulos = _inventariar_rotulos(pdf)
    elementos = []
    alertas = []
    mapa_rotulos = {(r["referencia"],r["pagina_pdf"]):r for r in rotulos}
    for region in config.regiones_especiales:
        rotulo = mapa_rotulos.get((region.referencia, region.pagina_pdf))
        if rotulo is None:
            alertas.append(f"No se encontró rótulo de {region.referencia} en página {region.pagina_pdf}")
            rotulo = {"titulo": ""}
        pagina = pdf[region.pagina_pdf-1]
        if region.tipo == "tabla":
            elementos.append(_procesar_tabla(pagina, region, rotulo, config))
        elif region.tipo == "figura":
            elementos.append(_procesar_figura(pagina, region, rotulo, config))
    cubiertos = {(e.referencia, e.pagina_pdf) for e in elementos}
    for rotulo in rotulos:
        if (rotulo["referencia"], rotulo["pagina_pdf"]) not in cubiertos:
            alertas.append(f"Elemento detectado sin tratamiento: {rotulo['referencia']} "
                           f"(PDF página {rotulo['pagina_pdf']})")
    for e in elementos:
        for err in e.errores:
            alertas.append(f"{e.referencia}: {err}")
    return elementos, rotulos, alertas


def plantilla_revision_visuales(resultado: Resultado) -> dict[str, Any]:
    """Plantilla local: revisa PDF, contenido y huella antes de aprobar."""
    return {
        e.id: {
            "referencia": e.referencia,
            "pagina_pdf": e.pagina_pdf,
            "titulo": e.titulo,
            "sha256": e.huella_sha256,
            "aprobado": False,
            "observaciones": "Comparar contra el elemento visual del PDF antes de aprobar",
            "descripcion": e.descripcion,
            "texto_extraido": e.texto_extraido,
            "filas": e.filas,
            "notas": e.notas,
            "errores": e.errores,
        } for e in resultado.elementos_visuales
    }


def preparar_norma(ruta_pdf: str | Path, config: ConfigNorma = CONFIG_NCH_ISO_14067) -> Resultado:
    """Detecta unidades por títulos negritas y reconstruye su texto entre páginas.

    El parser es reutilizable por configuración, no universal: cada nueva
    familia de normas requiere una prueba visual y validación de encabezados.
    """
    ruta_pdf = Path(ruta_pdf)
    if not ruta_pdf.is_file():
        raise FileNotFoundError(f"No existe el PDF: {ruta_pdf}")
    with fitz.open(ruta_pdf) as pdf:
        if len(pdf) < config.pagina_fin:
            raise ValueError(f"PDF de {len(pdf)} páginas; config llega a {config.pagina_fin}")
        elementos_visuales, rotulos_visuales, alertas_visuales = _extraer_visuales(pdf, config)
        lineas: list[Linea] = []
        conteos = Counter()
        for pagina_pdf in range(config.pagina_inicio, config.pagina_fin + 1):
            extraidas, stats = _extraer_lineas(pdf[pagina_pdf - 1], pagina_pdf, config)
            lineas.extend(extraidas)
            conteos.update(stats)

    unidades: list[Unidad] = []
    unidad: Unidad | None = None
    pendientes_titulo: list[str] = []
    ultimo_encabezado_y: float = -1
    tamano_encabezado: float = 0
    encabezados_detectados = 0
    for lin in lineas:
        encabezado = _identificar_encabezado(lin)
        if encabezado:
            if unidad is not None:
                unidades.append(unidad)
            numero, titulo = encabezado
            unidad = Unidad(
                apartado=numero, titulo=titulo,
                documento=config.documento,
                pagina_pdf_inicio=lin.pagina_pdf, pagina_pdf_fin=lin.pagina_pdf,
                caracter=_tipo_caracter(numero)
            )
            encabezados_detectados += 1
            ultimo_encabezado_y = lin.y
            tamano_encabezado = lin.tamano
            pendientes_titulo = []
            continue
        if unidad is None:
            # Ejemplo: título general en p. 13 antes de '1 Objeto...'.
            continue
        # Encabezados de apartado extensos, ej. E.2, pueden continuar en
        # una segunda línea negrita con la misma tipografía.
        if (not unidad.apartado.startswith("Anexo ") and not unidad.lineas
                and unidad.titulo and lin.negrita and lin.tamano >= 12
                and tamano_encabezado >= 12
                and lin.pagina_pdf == unidad.pagina_pdf_inicio
                and 0 < lin.y - ultimo_encabezado_y <= 23):
            unidad.titulo += " " + lin.texto
            ultimo_encabezado_y = lin.y
            continue
        # Las definiciones tienen '3.1.1.1' en una línea, y el título y sigla
        # aparecen en líneas negritas consecutivas.
        if not unidad.lineas and lin.negrita and lin.tamano >= 10.5 and (
            not unidad.titulo or pendientes_titulo
        ):
            pendientes_titulo.append(lin.texto)
            unidad.titulo = " / ".join(pendientes_titulo)
            continue
        # Encabezado central de anexo: (normativo) + título, no son requisitos.
        if unidad.apartado.startswith("Anexo ") and not unidad.lineas:
            if re.fullmatch(r"\((?:normativo|informativo)\)", lin.texto, flags=re.I):
                continue
            if lin.negrita and lin.tamano >= 13:
                pendientes_titulo.append(lin.texto)
                unidad.titulo = " ".join(pendientes_titulo)
                continue
        unidad.lineas.append(lin)
        unidad.pagina_pdf_fin = lin.pagina_pdf
    if unidad is not None:
        unidades.append(unidad)

    # El título de un anexo puede ocupar varias líneas: se une con espacios,
    # a diferencia de los sinónimos de una definición terminológica.
    for u in unidades:
        if u.apartado.startswith("Anexo "):
            u.titulo = u.titulo.replace(" / ", " ")

    alertas = []
    ids = [u.apartado for u in unidades]
    duplicados = [id_ for id_, veces in Counter(ids).items() if veces > 1]
    if duplicados:
        alertas.append(f"IDs de apartados duplicados: {duplicados}")
    # No se realizan comprobaciones ficticias de '100% de exactitud'.
    alertas.extend(alertas_visuales)
    if elementos_visuales:
        alertas.append("Elementos visuales preparados: requieren validación humana antes de indexarse")
    vacios = [u.apartado for u in unidades if not u.texto.strip()]
    estadisticas = {
        "documento": config.documento,
        "paginas_pdf_procesadas": config.pagina_fin - config.pagina_inicio + 1,
        "lineas_brutas": conteos["lineas_brutas"],
        "lineas_excluidas_geometria_y_ruido": conteos["lineas_excluidas"],
        "lineas_excluidas_en_regiones_especiales": conteos["lineas_region_especial"],
        "unidades_detectadas": len(unidades),
        "unidades_con_texto": len(unidades) - len(vacios),
        "unidades_sin_texto": vacios,
        "apartados_duplicados": duplicados,
        "caracteres_en_unidades": sum(len(u.texto) for u in unidades),
        "unidades_multpagina": [
            {"apartado": u.apartado, "desde": u.pagina_pdf_inicio, "hasta": u.pagina_pdf_fin}
            for u in unidades if u.pagina_pdf_fin > u.pagina_pdf_inicio
        ],
        "unidades_por_caracter": dict(Counter(u.caracter for u in unidades)),
        "regiones_especiales_pendientes": [
            {"referencia": r.referencia, "pagina_pdf": r.pagina_pdf, "tipo": r.tipo}
            for r in config.regiones_especiales
        ],
        "rotulos_visuales_detectados": len(rotulos_visuales),
        "elementos_visuales_procesados": len(elementos_visuales),
        "figuras_procesadas": sum(e.tipo == "figura" for e in elementos_visuales),
        "tablas_procesadas": sum(e.tipo == "tabla" for e in elementos_visuales),
        "filas_tabla_extraidas": sum(len(e.filas) for e in elementos_visuales),
        "visuales_con_error": [e.referencia for e in elementos_visuales if e.errores],
    }
    return Resultado(config, unidades, list(config.regiones_especiales), estadisticas,
                     alertas, elementos_visuales, rotulos_visuales)


def _control_puntos(resultado: Resultado) -> dict[str, Any]:
    mapa = {u.apartado: u for u in resultado.unidades}
    puntos = ["1", "3.1.1.1", "5.12", "6.3.4.3", "6.3.5", "6.4.6.2",
              "6.4.9.4.4", "6.4.9.8", "7.3", "8", "Anexo A", "Anexo B",
              "Anexo C", "Anexo D", "Anexo E", "E.2.1"]
    return {
        clave: {"detectado": clave in mapa,
                "pagina_pdf_inicio": mapa[clave].pagina_pdf_inicio if clave in mapa else None,
                "pagina_pdf_fin": mapa[clave].pagina_pdf_fin if clave in mapa else None,
                "tiene_texto": bool(mapa[clave].texto.strip()) if clave in mapa else False}
        for clave in puntos
    }


def validar_resultado(resultado: Resultado) -> dict[str, Any]:
    # Esta validación no certifica equivalencia completa con el PDF.
    contaminados = [u.apartado for u in resultado.unidades if PATRON_CONTAMINACION.search(u.texto)]
    validacion = {
        "contaminacion_repetitiva_detectada_en_unidades": contaminados,
        "apartados_de_control": _control_puntos(resultado),
        "paginas_registradas_correctamente": all(
            resultado.config.pagina_inicio <= u.pagina_pdf_inicio <= u.pagina_pdf_fin <= resultado.config.pagina_fin
            for u in resultado.unidades),
        "sin_ids_duplicados": not resultado.estadisticas["apartados_duplicados"],
        "visuales_aprobados": sum(e.aprobado for e in resultado.elementos_visuales),
        "visuales_pendientes": [e.referencia for e in resultado.elementos_visuales if not e.aprobado],
        # La revisión semántica integral de la norma sigue siendo un control humano.
        "requiere_revision_humana": True,
    }
    return validacion


def generar_diagnostico(resultado: Resultado) -> dict[str, Any]:
    return {
        "resumen": resultado.estadisticas,
        "controles": validar_resultado(resultado),
        "alertas": resultado.alertas,
        "inventario_visual": [
            {"referencia": e.referencia, "tipo": e.tipo,
             "pagina_pdf": e.pagina_pdf, "pagina_norma": e.pagina_norma,
             "apartado": e.apartado, "filas": len(e.filas),
             "estado": "aprobado" if e.aprobado else "pendiente_revision",
             "errores": e.errores, "huella_sha256": e.huella_sha256}
            for e in resultado.elementos_visuales
        ],
        "rotulos_detectados": resultado.rotulos_detectados,
        "limites": [
            "La detección depende de la tipografía y geometría del PDF original.",
            "Las tablas y figuras se extraen por separado y requieren aprobación humana antes de indexarse.",
            "La integridad semántica y fórmulas requieren comparación con el original.",
            "No se ha indexado ni generado embeddings; falta validar la licencia de uso.",
        ],
    }


def _json_canonico(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_archivo(ruta: Path) -> str:
    sha = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(bloque)
    return sha.hexdigest()


def _id_estable(documento: str, metadata: dict[str, Any]) -> str:
    """ID por identidad de unidad, independiente del orden o del texto de ésta."""
    clave = {
        "documento": documento,
        "apartado": metadata.get("apartado", ""),
        "tipo_contenido": metadata.get("tipo_contenido", ""),
        "referencia_visual": metadata.get("referencia_visual", ""),
        "fila_tabla": metadata.get("fila_tabla", 0),
    }
    return "norma_" + hashlib.sha256(_json_canonico(clave).encode("utf-8")).hexdigest()[:24]


def construir_corpus_serializable(resultado: Resultado, ruta_pdf: str | Path,
                                  exigir_aprobaciones: bool = True) -> dict[str, Any]:
    """Construye corpus validable, sin necesitar LangChain ni realizar llamadas a APIs.

    Con exigir_aprobaciones=True no admite la exportación parcial inadvertida.
    No sustituye la revisión de fidelidad de párrafos, fórmulas y geometría.
    """
    ruta_pdf = Path(ruta_pdf)
    if not ruta_pdf.is_file():
        raise FileNotFoundError(f"PDF original no encontrado: {ruta_pdf}")

    pendientes = [e.referencia for e in resultado.elementos_visuales
                  if not e.aprobado or e.errores]
    if exigir_aprobaciones and pendientes:
        raise ValueError("No se exportó el corpus: elementos visuales sin aprobación válida: "
                         + ", ".join(pendientes)
                         + ". Ejecutar con --aprobaciones RUTA_JSON.")

    controles = validar_resultado(resultado)
    if not controles["sin_ids_duplicados"] or not controles["paginas_registradas_correctamente"]:
        raise ValueError("No se exportó: falló la validación estructural de apartados")
    if controles["contaminacion_repetitiva_detectada_en_unidades"]:
        raise ValueError("No se exportó: se detectó contaminación repetitiva en apartados")
    faltantes = [clave for clave, info in controles["apartados_de_control"].items()
                 if not info["detectado"]]
    if faltantes:
        raise ValueError("No se exportó: faltan apartados de control: " + ", ".join(faltantes))

    registros = resultado.registros_corpus(solo_visuales_aprobados=True)
    documentos: list[dict[str, Any]] = []
    ids = set()
    for i, reg in enumerate(registros, 1):
        contenido = reg["page_content"]
        meta = reg["metadata"]
        if not isinstance(contenido, str) or not contenido.strip():
            raise ValueError(f"Documento {i} vacío")
        if not isinstance(meta, dict) or not meta.get("fuente") or not meta.get("apartado"):
            raise ValueError(f"Documento {i} sin fuente o apartado")
        if PATRON_CONTAMINACION.search(contenido):
            raise ValueError(f"Documento {i} contiene texto repetitivo de licencia o impresión")
        desde, hasta = meta.get("pagina_pdf_inicio"), meta.get("pagina_pdf_fin")
        if not isinstance(desde, int) or not isinstance(hasta, int) or desde > hasta:
            raise ValueError(f"Documento {i} contiene páginas inválidas")
        identidad = _id_estable(resultado.config.documento, meta)
        if identidad in ids:
            raise ValueError(f"ID estable duplicado en documento {i}: {identidad}")
        ids.add(identidad)
        documentos.append({"id": identidad, "page_content": contenido, "metadata": meta})

    esperados_texto = resultado.estadisticas["unidades_con_texto"]
    visuales = [e for e in resultado.elementos_visuales if e.aprobado]
    esperados_visual = sum(len(e.registros_corpus()) for e in visuales)
    if len(documentos) != esperados_texto + esperados_visual:
        raise ValueError("No se exportó: recuento de documentos distinto del esperado")
    huella_contenido = hashlib.sha256(_json_canonico(documentos).encode("utf-8")).hexdigest()
    return {
        "schema_version": VERSION_ESQUEMA_CORPUS,
        "documento": resultado.config.documento,
        "pdf_original": ruta_pdf.name,
        "pdf_sha256": _sha256_archivo(ruta_pdf),
        "procesamiento": "Segmentación por apartados normativos + representaciones visuales aprobadas",
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "estadisticas": {
            "unidades_estructurales": len(resultado.unidades),
            "documentos_texto": esperados_texto,
            "documentos_visuales": esperados_visual,
            "figuras_aprobadas": sum(e.aprobado and e.tipo == "figura"
                                    for e in resultado.elementos_visuales),
            "tablas_aprobadas": sum(e.aprobado and e.tipo == "tabla"
                                   for e in resultado.elementos_visuales),
            "documentos_total": len(documentos),
        },
        "corpus_sha256": huella_contenido,
        "documentos": documentos,
    }


def exportar_corpus_json(resultado: Resultado, ruta_pdf: str | Path,
                         ruta_salida: str | Path = RUTA_CORPUS) -> dict[str, Any]:
    """Persiste corpus protegido en disco LOCAL; exige TODAS las aprobaciones.

    Se escribe de forma atómica para no dejar corpus incompleto ante errores.
    Evitar incluir data/corpus en Git, backups compartidos o sincronizaciones.
    """
    contenido = construir_corpus_serializable(resultado, ruta_pdf, exigir_aprobaciones=True)
    destino = Path(ruta_salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".tmp",
                                         prefix=".corpus_", dir=destino.parent,
                                         delete=False) as f:
            temporal = Path(f.name)
            json.dump(contenido, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        temporal.replace(destino)
    finally:
        if temporal is not None and temporal.exists():
            temporal.unlink()
    return {"ruta": str(destino), **contenido["estadisticas"],
            "pdf_sha256": contenido["pdf_sha256"],
            "corpus_sha256": contenido["corpus_sha256"]}


def cargar_corpus_json(ruta: str | Path):
    """Carga el JSON persistido en List[Document] para rag_indexer.py.

    Requiere langchain-core únicamente durante la carga, no durante la exportación.
    Comprueba que el corpus no haya cambiado desde su generación.
    """
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    if datos.get("schema_version") != VERSION_ESQUEMA_CORPUS:
        raise ValueError("Versión de esquema de corpus no compatible")
    registros = datos.get("documentos", [])
    if not isinstance(registros, list) or len(registros) != datos.get("estadisticas", {}).get("documentos_total"):
        raise ValueError("Corpus incompleto: recuento de documentos incorrecto")
    actual = hashlib.sha256(_json_canonico(registros).encode("utf-8")).hexdigest()
    if actual != datos.get("corpus_sha256"):
        raise ValueError("El contenido del corpus fue modificado (SHA-256 no coincide)")
    try:
        from langchain_core.documents import Document
    except ImportError as exc:
        raise RuntimeError("Para cargar Document instale langchain-core (dependencias del curso)") from exc
    return [Document(page_content=r["page_content"], metadata=r["metadata"])
            for r in registros]


def main() -> None:
    """Prepara y valida el documento local, sin usar Gemini ni Chroma.

    Desde la raíz del proyecto:
        python -m src.preparar_norma

    También permite indicar otro PDF y otro destino del reporte:
        python -m src.preparar_norma "C:\\ruta\\otra_norma.pdf" --reporte "reporte.json"
    """
    parser = argparse.ArgumentParser(
        description="Inspección y estructuración de una norma PDF (sin llamadas a APIs)"
    )
    parser.add_argument(
        "pdf", nargs="?", type=Path, default=RUTA_NORMA,
        help=f"Ruta al PDF (por defecto: {RUTA_NORMA})",
    )
    parser.add_argument(
        "--reporte", type=Path, default=RUTA_REPORTE,
        help=f"Destino del diagnóstico JSON (por defecto: {RUTA_REPORTE})",
    )
    parser.add_argument(
        "--revision-visuales", type=Path,
        default=PROJECT_ROOT / "data" / "revision_visuales_iso14067.json",
        help="Plantilla local para validar todos los elementos visuales"
    )
    parser.add_argument(
        "--aprobaciones", type=Path, default=None,
        help="JSON de revisiones aprobadas con sha256 correcto, si existe"
    )
    parser.add_argument(
        "--exportar-corpus", action="store_true",
        help="Generar corpus JSON local tras comprobar todas las aprobaciones"
    )
    parser.add_argument(
        "--salida-corpus", type=Path, default=RUTA_CORPUS,
        help=f"Ubicación del corpus estructurado (por defecto: {RUTA_CORPUS})"
    )
    args = parser.parse_args()

    resultado = preparar_norma(args.pdf)
    if args.aprobaciones:
        aprobaciones = json.loads(args.aprobaciones.read_text(encoding="utf-8"))
        resultado.alertas.extend(resultado.aprobar_visuales(aprobaciones))
    args.revision_visuales.parent.mkdir(parents=True, exist_ok=True)
    if not args.revision_visuales.exists():
        args.revision_visuales.write_text(
            json.dumps(plantilla_revision_visuales(resultado), ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    # La alerta genérica inicial no describe el estado tras aplicar aprobaciones.
    if resultado.elementos_visuales and all(e.aprobado for e in resultado.elementos_visuales):
        resultado.alertas = [a for a in resultado.alertas if not a.startswith(
            "Elementos visuales preparados: requieren validación humana")]
    diagnostico = generar_diagnostico(resultado)
    args.reporte.parent.mkdir(parents=True, exist_ok=True)
    args.reporte.write_text(
        json.dumps(diagnostico, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    info_corpus = None
    if args.exportar_corpus:
        try:
            info_corpus = exportar_corpus_json(resultado, args.pdf, args.salida_corpus)
        except (ValueError, OSError) as exc:
            parser.error(str(exc))
    print(json.dumps({
        "documento": str(args.pdf),
        "unidades": resultado.estadisticas["unidades_detectadas"],
        "con_texto": resultado.estadisticas["unidades_con_texto"],
        "alertas": resultado.alertas,
        "reporte": str(args.reporte),
        "revision_visuales": str(args.revision_visuales),
        "elementos_visuales": len(resultado.elementos_visuales),
        "corpus_exportado": info_corpus,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
