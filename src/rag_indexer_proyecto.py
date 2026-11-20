from dotenv import load_dotenv #importa variables de entorno
from langchain_text_splitters import RecursiveCharacterTextSplitter #función para dividir (chunking)
from langchain_google_genai import GoogleGenerativeAIEmbeddings #embedding de Gemini
from langchain_chroma import Chroma #Chroma = vector store
from langchain_core.documents import Document

load_dotenv()
"""
Auditar localmente que no haya chunks vacíos ni duplicados antes de gastar tokens en embeddings
"""
def verificar_integridad(chunks, corpus_original):
    #Recorrer todos los chunks con su indice (i), quitamos espacios/saltos de línea
    #guardo lista de posiciones de cualquier fragmento que haya quedado en blanco
    vacios = [i for i, c in enumerate(chunks) if not c.page_content.strip()]

    #Extraigo el texto plano de cada objeto, lista
    textos = [c.page_content for c in chunks]

    #lista1 = ["manzana", "pera", "manzana", "uvas"]
    #set1 = ["manzana", "pera", "uvas"]

    #Set/Conjunto es una lista de valores únicos
    #Convierto la lista de textos en un set (para eliminar repetidos automáticamente), y si la longitud es distinta a la original significa que tenemos chunks iguales
    hay_duplicados = len(textos) != len(set(textos))

    if vacios:
        raise ValueError(f"Se detectaron chunks vacíos en los índices: {vacios}")
    if hay_duplicados:
        print("Advertencia: Se detectaron chunks duplicados en el corpus.")

    #Sumar el otal de caracteres de todos los chunks generados vs. el total de caracteres del corpus original
    total_chars_chunks = sum(len(c.page_content) for c in chunks)
    total_chars_corpus = sum(len(d) for d in corpus_original)

    print(f"Integridad OK | Chunks: {len(chunks)} | Caracteres (corpus/chunks): {total_chars_corpus}/{total_chars_chunks}")

# Adaptación mínima para corpus normativos preparados por src.preparar_norma.
# Las funciones originales del curso se conservan. Sólo se agrega un modo
# con IDs persistentes y protección de elementos visuales completos.
TIPOS_VISUALES_INDIVISIBLES = {"figura", "tabla_fila", "tabla_resumen"}


def preparar_chunks(corpus, chunk_size=200, chunk_overlap=30, es_documento=False):
    """Divide en fragmentos respetando los límites de los Documents de entrada.

    Devuelve (chunks, ids) con IDs estables cuando cada Document trae
    metadata['unidad_id']. Las filas de tabla y figuras aprobadas se conservan
    enteras para no romper relaciones visuales o columnas.

    No genera embeddings, ni llama a APIs y puede usarse en modo diagnóstico.
    """
    if chunk_size <= 0 or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("Se requiere chunk_size > 0 y 0 <= chunk_overlap < chunk_size")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    if not es_documento:
        chunks = splitter.create_documents(corpus)
        return chunks, None

    chunks = []
    ids = []
    usar_ids = all(bool(doc.metadata.get("unidad_id")) for doc in corpus)
    if any(bool(doc.metadata.get("unidad_id")) for doc in corpus) and not usar_ids:
        raise ValueError("Corpus con 'unidad_id' parcial: deben tenerlo todos los Documents")

    for doc in corpus:
        if not doc.page_content.strip():
            raise ValueError("El corpus contiene documentos vacíos")
        # Esta distinción no modifica los metadatos ni el texto original.
        if doc.metadata.get("tipo_contenido") in TIPOS_VISUALES_INDIVISIBLES:
            subchunks = [doc]
        else:
            subchunks = splitter.split_documents([doc])
        for numero, parte in enumerate(subchunks):
            parte.metadata = dict(parte.metadata)
            parte.metadata["chunk_orden"] = numero
            chunks.append(parte)
            if usar_ids:
                ids.append(f"{doc.metadata['unidad_id']}_c{numero:04d}")

    if usar_ids and len(ids) != len(set(ids)):
        raise ValueError("Se detectaron IDs repetidos después del chunking")
    return chunks, ids if usar_ids else None


"""
Recibir un corpus/texto dividirlo, calcular el embedding, y guardar el corpus en mi vector store
"""
def indexar_corpus(corpus, persist_directory, chunk_size=200, chunk_overlap=30, es_documento=False):
    # Mismo flujo del curso: chunking -> embeddings de Gemini -> Chroma.
    # La preparación por apartados y los IDs estables son opcionales.
    chunks, ids_estables = preparar_chunks(
        corpus, chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        es_documento=es_documento,
    )
    if not chunks:
        raise ValueError("No hay chunks para indexar")

    # Comprobación local antes de consumir API para embeddings.
    verificar_integridad(
        chunks,
        [d.page_content for d in corpus] if es_documento else corpus,
    )

    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    parametros = {
        "documents": chunks,
        "embedding": embeddings,
        "persist_directory": str(persist_directory),
    }
    if ids_estables:
        parametros["ids"] = ids_estables
    vector_store = Chroma.from_documents(**parametros)
    return vector_store

"""
Función que abre/carga la carpeta existente del disco para leerla. NO GASTO TOKENS
"""
def cargar_vectorstore(persist_directory):
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    return Chroma(persist_directory=persist_directory, embedding_function=embeddings)

def eliminar_por_ids(vectorstore, ids_a_borrar):
    vectorstore.delete(ids=ids_a_borrar)

def agregar_documentos(vectorstore, nuevos_textos, prefijo_id, chunk_size=200, chunk_overlap=30):
    #doc_
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    nuevo_chunks = splitter.create_documents(nuevos_textos) #Lista de los fragmentos

    #Crear los ids
    ids_nuevos = [f"{prefijo_id}_{i}" for i in range(len(nuevo_chunks))] #["doc_0", "doc_1", "doc_2"]

    #ids_nuevos = []
    #for i in range(len(nuevo_chunks)):
    #   ids_nuevos.append(f"{prefijo_id}_{i}"")

    verificar_integridad(nuevo_chunks, nuevos_textos)

    try:
        vectorstore.add_documents(ids=ids_nuevos, documents=nuevo_chunks)
        #vectorstore.add_documents(nuevo_chunks, ids_nuevos)
        print(f"Agregados {len(nuevo_chunks)} chunks con el prefijo {prefijo_id}")
    except Exception as error:
        print("Error al agregrar nuevos documentos: ", error)

"""
Realiza la búsqueda semántica (por significado, NO POR PALABRA EXACTA) en el vector store.
Devuelve una lista con los resultados semejantes
"""
def buscar_similares(vectorstore, pregunta, k=3):
    #El modelo (Gemini) se encarga únicamente de hacer la traducción de la pregunta a vectores numéricos (gasta tokens)
    #Chroma se encarga de regresarme la lista con los chunks más parecidos
    #Chroma mide la distancia Euclidiana (L2). Entre más bajo sea el número, más cercano es el significado.
    resultados = vectorstore.similarity_search_with_score( #with_score regresa también la distancia euclidiana
        query=pregunta, #Gastamos tokens en traducir la pregunta a vectores numéricos
        k=k #La cantidad de chunks que quiero que regrese
    )

    #resultados = [ {"page_content": "CONTENIDO DEL CHUNK", "metadata": {"fuente": "documento.pdf"}}, {}, {} ]

    #iterar para imprimir todos los resultados
    for i, (doc, score)in enumerate(resultados, start=1):
        print(f"[Resultado {i}] Distancia (score): {score:.4f}")
        print(f"Contenido: {doc.page_content}")
        if doc.metadata:
            print(f"Metadata: {doc.metadata}")

    return resultados

def formatear_contexto(chunks_recuperados):
    lineas = []
    citas = {}

    """
    chunks_recuperados = [

        {
            "page_content": "El usuario puede iniciar 3 veces sesión",
            "metadata": {
                "fuente": "manual_de_usuario.txt",
                "fecha": "2026-11-13"
            }
        },
        {},
        {}

    ]
    """

    for i, doc in enumerate(chunks_recuperados, start=1):
        #Si el chunk no se indexó con metadata["fuente"], devolverá "desconocida"
        fuente = doc.metadata.get("fuente", "desconocida") #"manual_de_usuario.txt"
        lineas.append(f"[{i}] {doc.page_content}") # [1] "El usuario puede iniciar 3 veces sesión"
        citas[i] = fuente #{1: "manual_de_usuario.txt"}

    contexto = "\n\n".join(lineas)
    return contexto, citas

#¿Cuál es el ID de cada chunk?
def inspeccionar_chunks(vectorstore):
    datos = vectorstore.get()
    #datos["ids"], datos["documents"], datos["metadatas"]
    total = len(datos["ids"])
    print(f"-- INVENTARIO DE CHUNKS EN CHROMA (Total: {total}) --")

    """
    [
        (579517b3-b962-4d38-aaae-def944b4e486, El cliente reintenta hasta 3 veces ante un TimeoutError, con espera creciente...., None),
        (233bfcaa-0650-433e-803c-e1d83235259a, El costo de cada llamada se calcula a partir de totalTokenCount...., None),
    ]

    chunk_id = 579517b3-b962-4d38-aaae-def944b4e486
    texto = El cliente reintenta hasta 3 veces ante un TimeoutError, con espera creciente....
    meta = None
    """
    for i, (chunk_id, texto, meta) in enumerate(zip(datos["ids"], datos["documents"], datos["metadatas"]), start=1):
        print(f"[{i}] ID: {chunk_id}")
        print(f"Fuente/Meta: {meta}")
        resumen = texto.replace("\n", " ") #Quita los saltos de línea y obten solo los primeros 100 caracteres
        print(f"Contenido: {resumen}...")

if __name__ == "__main__":
    #Constante
    CARPETA_DB = "vectorstore_ejemplo"

    # corpus = [
    #     "El cliente reintenta hasta 3 veces ante un TimeoutError, con espera creciente.",
    #     "El costo de cada llamada se calcula a partir de totalTokenCount.",
    #     "Las pruebas unitarias del cliente usan mocks y corren en menos de un segundo.",
    # ]

    # #indexar_corpus(corpus, CARPETA_DB) #Almacenar el texto
    # #indexar_corpus(corpus=corpus, persist_directory=CARPETA_DB, chunk_size=250, chunk_overlap=35)

    # vs = cargar_vectorstore(CARPETA_DB) #Cargar la carpeta para poder consultarla/actualizarla más adelante
    # print("Chunks indexados: ", vs._collection.count()) #Imprime los chunks indexados

    # datos = vs.get()
    # print("IDs almacenados: ", datos["ids"])
    # print("Chunks almacenados: ", datos["documents"])

    # #eliminar_por_ids(["579517b3-b962-4d38-aaae-def944b4e486"])

    # nueva_politica = ["Los envíos nacionales tardan entre 5 y 10 días hábiles"]
    # #agregar_documentos(vs, nueva_politica, "doc_nuevo", 150, 20)
    # agregar_documentos(
    #     vectorstore=vs,
    #     nuevos_textos=nueva_politica,
    #     prefijo_id="doc_nuevo",
    #     chunk_size=150,
    #     chunk_overlap=20
    # )

    # datos = vs.get()
    # print("IDs almacenados: ", datos["ids"])
    # print("Chunks almacenados: ", datos["documents"])

    vs = cargar_vectorstore(CARPETA_DB)
    # pregunta = "¿Qué hace el sistema cuando hay un fallo de red o tiempo de espera?"

    # chunks_recuperados = buscar_similares(vs, pregunta, k=2)

    # #k = Cantidad de chunks que quiero que regrese
    # retrievier = vs.as_retriever(search_kwargs={"k": 2}) #Adapta lo que tenía en Chroma para poder utilizarlo en LangChain
    # #Ventaja principal: Cadena o Agente |
    # resultados = retrievier.invoke("¿Cuánto tarda un envío en el mismo país?")
    # for r in resultados:
    #     print(r.page_content)

    #Instalación adicional si queremos leer pdf, docs, etc
    with open("manual_de_usuario.txt", "r", encoding="utf-8") as f: #r: read, a: append, w: write
        contenido = f.read()

    documentos = [Document(page_content=contenido, metadata={"fuente": "manual_de_usuario.txt", "fecha": "2026-11-13"})]

    #indexar_corpus(documentos, CARPETA_DB, es_documento=True) #comentado para que no vuelvan a ingresar el manual de usuario en su vs

    datos = vs.get()
    print("IDs almacenados: ", datos["ids"])
    print("Chunks almacenados: ", datos["documents"])

    retriever = vs.as_retriever(search_kwargs={"k": 2})
    # chunks_recuperados = retriever.invoke("¿Cuantos reintentos tengo ante un error?")

    # contexto, citas = formatear_contexto(chunks_recuperados)
    # print("--CONTEXTO FORMATEADO--")
    # print(contexto)
    # print("--DICCIONARIO DE CITAS--")
    # print(citas)

    inspeccionar_chunks(vs)

    #consulta: "Cuáles son los errores de credenciales inválidas?"
    #ids_relevantes = {"a4bc644f-ffa9-4219-94b2-5fd7cff518be"}

    #*****ADVERTENCIA***** Código para borrar todo mi vectorstore
    # if os.path.exists(CARPETA_DB):
    #     shutil.rmtree(CARPETA_DB)
