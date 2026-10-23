# Repositorio Gate 1: Especialización en Desarrollo con IA Generativa (Accenture)

Este repositorio es el punto de partida del proyecto que estoy desarrollando en la Especialización en Desarrollo con IA Generativa de Accenture. En Gate 1 preparé la estructura de trabajo y probé la clonación del repositorio. A medida que avance el programa, iré incorporando código, documentación y pruebas hasta completar la aplicación que presentaré en Gate 3.

En este README explico cómo instalé el proyecto después de clonarlo y cómo otra persona puede repetir el proceso en Windows (PowerShell) o macOS (Terminal). Los pasos están ordenados para seguirlos desde una copia nueva del repositorio.

## Requisitos previos

Antes de comenzar, necesitas:

- Git instalado.
- Python 3 instalado.
- PowerShell en Windows o Terminal en macOS.
- Una clave de API de Gemini para ejecutar los scripts que consultan el modelo.

Comprueba que Git y Python estén disponibles.

**Windows (PowerShell):**

```powershell
git --version
python --version
```

**macOS (Terminal):**

```bash
git --version
python3 --version
```

## Instalación paso a paso

### 1. Clonar el repositorio

Abre PowerShell o Terminal y sitúate en la carpeta donde quieras guardar el proyecto. Ejecuta:

```bash
git clone https://github.com/pzuniga/ProyectoIA_Skillnest.git ProyectoIA_Skillnest_Gate_1
cd ProyectoIA_Skillnest_Gate_1
```

El comando `git clone` descarga el repositorio y crea una carpeta local llamada `ProyectoIA_Skillnest_Gate_1`. El nombre local puede ser distinto del nombre del repositorio remoto. El segundo comando entra en la carpeta; desde ahí ejecutarás los pasos siguientes.

Si ya clonaste el proyecto, no repitas `git clone` en la misma ubicación. Entra a la carpeta existente y, para descargar cambios del repositorio remoto, ejecuta:

```bash
git pull
```

### 2. Crear el entorno virtual

Creé un entorno virtual propio para este proyecto, de modo que sus paquetes de Python no se mezclen con los de otros proyectos. Ejecuta el comando desde la carpeta `ProyectoIA_Skillnest_Gate_1`.

**Windows (PowerShell):**

```powershell
python -m venv venv
```

**macOS (Terminal):**

```bash
python3 -m venv venv
```

El comando crea la carpeta local `venv`. Solo necesitas crear el entorno una vez por copia del proyecto.

### 3. Activar el entorno virtual

**Windows (PowerShell):**

```powershell
.\venv\Scripts\Activate.ps1
```

Si PowerShell impide la activación por la política de ejecución, permite scripts locales para tu usuario y vuelve a ejecutar el comando de activación:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\venv\Scripts\Activate.ps1
```

**macOS (Terminal):**

```bash
source venv/bin/activate
```

Cuando la activación funciona, normalmente aparece `(venv)` al comienzo de la línea de la terminal. Comprueba que Python corresponde al entorno virtual.

**Windows (PowerShell):**

```powershell
Get-Command python
python --version
```

**macOS (Terminal):**

```bash
which python
python --version
```

La ruta de Python debe apuntar a la carpeta `venv` del proyecto. Para salir del entorno virtual al terminar de trabajar, ejecuta:

```bash
deactivate
```

### 4. Instalar las dependencias

Con el entorno virtual activo y desde la carpeta raíz del proyecto, instala las dependencias declaradas en `requirements.txt`:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Si el comando indica que no encuentra el archivo, confirma que estás en la carpeta `ProyectoIA_Skillnest_Gate_1` y que `requirements.txt` aparece en ella.

### 5. Configurar la clave de Gemini

El proyecto usa variables de entorno para mantener las credenciales fuera del código. Copia `.env.example` a un archivo local llamado `.env`.

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
```

**macOS (Terminal):**

```bash
cp .env.example .env
```

Abre `.env` con un editor de texto y reemplaza el valor de ejemplo por tu clave. La variable utilizada por el proyecto es `GEMINI_API_KEY`:

```dotenv
GEMINI_API_KEY=tu_clave_real
```

No escribas la clave directamente en el código ni la compartas en capturas o mensajes. El archivo `.env` está excluido de Git mediante `.gitignore`, por lo que no se sube al repositorio.

### 6. Ejecutar el script principal

Con el entorno virtual activo, las dependencias instaladas y la clave configurada, ejecuta desde la carpeta raíz:

```bash
python src/consumir_gemini.py
```

El script envía una consulta a Gemini y muestra la respuesta del modelo. Para ejecutarlo necesitas conexión a internet, una clave válida y acceso al modelo configurado en el código.

Para ejecutar el benchmark que está incluido en el repositorio, utiliza:

```bash
python src/consumir_gemini_benchmark.py
```

El benchmark consulta los modelos definidos en el script y presenta mediciones de latencia y costo según los precios configurados allí.

## Estructura del proyecto

El árbol siguiente incluye únicamente carpetas y archivos que forman parte del repositorio. Revisé `.gitignore` para excluir los elementos locales que Git no versiona, como `.env`, `venv/`, `local_py/`, `__pycache__/` y los archivos compilados de Python.

```text
ProyectoIA_Skillnest_Gate_1/                         # Carpeta local creada al clonar el repositorio
├── .env.example                                      # Plantilla de la variable GEMINI_API_KEY, sin credenciales reales
├── .gitignore                                        # Reglas para excluir secretos, entornos y archivos locales
├── README.md                                         # Presentación del proyecto e instrucciones de instalación
├── requirements.txt                                  # Dependencias de Python y versiones declaradas
├── docs/                                             # Documentación y evidencias técnicas del proyecto
│   ├── .gitkeep                                      # Marcador para mantener la carpeta en Git
│   ├── decision_arquitectura.md                      # Decisión de arquitectura y comparación de modelos
│   ├── decision_arquitectura_salida.txt              # Registro de salida asociado al análisis de arquitectura
│   ├── diagrama_arquitectura.drawio                  # Diagrama de arquitectura editable
│   ├── diagrama_arquitectura.png                     # Exportación en imagen del diagrama de arquitectura
│   ├── evidencia_peticion_autenticada_1.png          # Evidencia visual de una petición autenticada
│   └── evidencia_peticion_autenticada_2.png          # Segunda evidencia visual de una petición autenticada
├── src/                                              # Código fuente que forma parte del repositorio
│   ├── .gitkeep                                      # Marcador que conserva la carpeta de código en Git
│   ├── consistencia.py                               # Ejecuta prompts y registra respuestas que cumplen el esquema
│   ├── consumir_gemini.py                            # Envía una consulta a Gemini y procesa la respuesta
│   ├── consumir_gemini_benchmark.py                  # Compara latencia y costo de los modelos configurados
│   └── prompts/                                      # Banco de prompts y resultados registrados
│       ├── banco.py                                  # Define prompts, instrucciones y esquemas de respuesta
│       └── registro_resultados.json                  # Guarda los resultados de consistencia en formato JSON
└── tests/                                            # Carpeta destinada a las pruebas del proyecto
    └── .gitkeep                                      # Marcador para mantener la carpeta de pruebas en Git
```

Las carpetas `docs/`, `src/` y `tests/` contienen archivos `.gitkeep` para conservarlas en Git aunque todavía tengan pocos archivos de trabajo. El árbol no muestra `.env`, `venv/` ni `local_py/`: son elementos locales excluidos por `.gitignore`. La carpeta `local_py/` contiene scripts de prueba y depuración que no se incluyen al clonar el repositorio.

## Registro del ensayo de instalación limpia

El 22 de octubre de 2026 realicé un ensayo de instalación limpia para comprobar el acceso al repositorio. Registro los resultados que confirmé:

| Campo | Resultado |
|---|---|
| Fecha | 22/10/2026 |
| Encontrado | No registré observaciones específicas durante el ensayo. |
| Corregido | No registré una corrección específica. |
| Resultado | La clonación del repositorio se completó satisfactoriamente. |
| Pendiente de registrar | La creación del entorno virtual, la instalación de dependencias, la configuración de `.env` y la ejecución de los scripts deben registrarse cuando se comprueben en una instalación limpia. |

Para repetir la prueba desde cero, clona el repositorio en una ubicación limpia y sigue los pasos de instalación de este README. No es necesario mantener dos copias para trabajar en el proyecto.

## Reglas que sigo durante el programa

- No incluyo contraseñas, claves de API ni tokens en el código o en archivos que subo al repositorio.
- Mantengo un entorno virtual separado para cada proyecto.
- Guardo el trabajo del programa en el repositorio de GitHub y excluyo los archivos locales que contienen secretos.
- Actualizo este README cuando cambian los pasos de instalación, las dependencias o la estructura del proyecto.

## Solución de problemas

- **La terminal no reconoce `git` o `python`:** comprueba que Git y Python estén instalados y vuelve a abrir la terminal. En macOS utiliza `python3` para crear el entorno virtual.
- **No aparece `(venv)` después de activar:** confirma que estás dentro de `ProyectoIA_Skillnest_Gate_1` y ejecuta el comando de activación correspondiente a tu sistema.
- **PowerShell bloquea la activación:** ejecuta `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a activar el entorno.
- **No se encuentra `requirements.txt`:** verifica que estás en la carpeta raíz del repositorio clonado.
- **No se encuentra `.env.example`:** comprueba que la clonación terminó correctamente y que estás en la carpeta del proyecto.
- **Gemini devuelve un error de autenticación:** revisa que `.env` contenga `GEMINI_API_KEY` y que la clave sea válida.
- **La solicitud no se completa:** comprueba la conexión a internet y vuelve a ejecutar el script. Si aparece un código de error, anótalo para diagnosticar el problema.

---

**Proyecto:** `ProyectoIA_Skillnest_Gate_1`  
**Etapa:** Gate 1  
**Programa:** Especialización en Desarrollo con IA Generativa (Accenture)
