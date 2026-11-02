from dotenv import load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

load.dotenv()

#api_key = os.getenv("API_KEY_AI")
#modelo = ChatGoogleGenerativeAI(model="geimini-3.6-flash", api_key=api_key)
modelo = ChatGoogleGenerativeAI(model="gemini-3.6.flash")
#respuesta = modelo.invoke("Qué es un token?")
print(respuesta.content)

#f-string
plantilla = PromptTemplate.from_template(
    "Explica el concepto de {tema} en un párrafo, para que alguien que recien comienza en {area}"
)

prompt = plantilla.invoke(
    {"tema": "tokenización", "area": "procesamiento de texto"}
)

print(prompt.text)
