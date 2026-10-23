# Repositorio Gate 1: Especialización en Desarrollo con IA Generativa (Accenture)

Este repositorio es el punto de partida del proyecto que estoy desarrollando en la Especialización en Desarrollo con IA Generativa de Accenture. En Gate 1 preparé la estructura inicial, configuré el entorno de Python y comprobé que el código pudiera consultar la API de Gemini. Iré ampliando el proyecto durante el programa hasta llegar a la aplicación que presentaré en Gate 3.

En este README dejo las instrucciones que seguí para instalar y ejecutar el proyecto, junto con el registro de un ensayo realizado desde una clonación limpia. Las instrucciones de instalación están dirigidas a Windows (PowerShell) y macOS (Terminal).

## Requisitos previos

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

Abre PowerShell o Terminal y sitúate en la carpeta donde quieras guardar el proyecto. El siguiente comando crea una carpeta local llamada `ProyectoIA_Skillnest_Gate_1`:

```bash
git clone https://github.com/pzuniga/ProyectoIA_Skillnest.git ProyectoIA_Skillnest_Gate_1
cd ProyectoIA_Skillnest_Gate_1
```

Si ya clonaste el repositorio en esa ubicación, no repitas `git clone`. Entra en la carpeta existente y, para descargar cambios del repositorio remoto, ejecuta:

```bash
git pull
```

### 2. Crear el entorno virtual

Creé un entorno virtual propio para este proyecto, de modo que sus paquetes no se mezclen con los de otros proyectos. Ejecuta el comando desde la carpeta `ProyectoIA_Skillnest_Gate_1`.

**Windows (PowerShell):**

```powershell
python -m venv venv
```

**macOS (Terminal):**

```bash
python3 -m venv venv
```

La carpeta `venv/` se crea localmente y está excluida del repositorio. Solo necesitas crearla una vez por copia del proyecto.

### 3. Activar y comprobar el entorno virtual

**Windows (PowerShell):**

```powershell
.\venv\Scripts\Activate.ps1
```

Si PowerShell impide la activación por su política de ejecución, puedes permitir scripts solo durante la sesión actual. Esta opción no cambia la política de forma permanente:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

**macOS (Terminal):**

```bash
source venv/bin/activate
```

Al activarse, normalmente aparece `(venv)` al comienzo de la línea de la terminal. Comprueba que se esté usando el Python del entorno virtual.

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

La ruta de Python debe apuntar a `venv` dentro del proyecto. Para salir del entorno virtual al terminar, ejecuta:

```bash
deactivate
```

### 4. Instalar las dependencias

Con el entorno virtual activo y desde la carpeta raíz del proyecto, instala las dependencias declaradas en `requirements.txt`:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. Configurar la clave de Gemini

Copia `.env.example` a un archivo local llamado `.env`.

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
```

**macOS (Terminal):**

```bash
cp .env.example .env
```

Abre `.env` con un editor de texto y reemplaza el valor de ejemplo por tu clave. El código espera la variable `GEMINI_API_KEY`:

```dotenv
GEMINI_API_KEY=tu_clave_real
```

No escribas la clave directamente en el código ni la compartas en capturas o mensajes. `.env` está excluido por `.gitignore` y no debe aparecer entre los archivos versionados.

### 6. Ejecutar el código

Con el entorno activo, las dependencias instaladas y `.env` configurado, ejecuta desde la carpeta raíz:

```powershell
python .\src\consumir_gemini.py
```

El script envía una consulta a Gemini e imprime la respuesta del modelo, la latencia observada y una estimación del costo de la petición. Necesitas conexión a internet, una clave válida y acceso al modelo configurado en el código.

También puedes ejecutar el benchmark incluido en el repositorio:

```powershell
python .\src\consumir_gemini_benchmark.py
```

Este script compara los modelos que tiene configurados y presenta mediciones de latencia y costo según los precios definidos en el propio código.

## Estructura del proyecto

Este árbol incluye los archivos que forman parte del repositorio. Revisé `.gitignore` y omití los elementos locales excluidos, entre ellos `.env`, `venv/`, `local_py/`, `__pycache__/` y los archivos compilados de Python.

```text
ProyectoIA_Skillnest_Gate_1/                  # Copia local del repositorio
├── .env.example                               # Plantilla de variables de entorno, sin credenciales reales
├── .gitignore                                 # Reglas de exclusión para archivos locales y secretos
├── README.md                                  # Descripción, instalación y registro del ensayo
├── requirements.txt                           # Dependencias de Python instaladas en el entorno
├── docs/                                      # Documentación y evidencias técnicas
│   ├── .gitkeep                               # Conserva la carpeta en Git
│   ├── decision_arquitectura.md               # Decisión y comparación de modelos
│   ├── decision_arquitectura_salida.txt       # Salida de apoyo al análisis de arquitectura
│   ├── diagrama_arquitectura.drawio           # Diagrama editable
│   ├── diagrama_arquitectura.png              # Diagrama exportado como imagen
│   ├── evidencia_peticion_autenticada_1.png   # Evidencia visual de una petición autenticada
│   └── evidencia_peticion_autenticada_2.png   # Segunda evidencia visual de una petición autenticada
├── src/                                       # Código fuente versionado
│   ├── .gitkeep                               # Conserva la carpeta en Git
│   ├── consistencia.py                        # Evalúa prompts y registra respuestas válidas
│   ├── consumir_gemini.py                     # Consulta Gemini y procesa la respuesta
│   ├── consumir_gemini_benchmark.py           # Mide latencia y costo de modelos configurados
│   └── prompts/                               # Prompts y resultados de evaluación
│       ├── banco.py                           # Instrucciones, ejemplos y esquemas de respuesta
│       └── registro_resultados.json           # Resultados de las pruebas de consistencia
└── tests/                                     # Carpeta destinada a las pruebas del proyecto
    └── .gitkeep                               # Conserva la carpeta en Git
```

Los archivos `.gitkeep` permiten conservar `docs/`, `src/` y `tests/` en Git. Las carpetas y archivos locales excluidos por `.gitignore` no aparecen al clonar el repositorio; cada persona debe crear su propio entorno `venv/` y archivo `.env` siguiendo las instrucciones anteriores. `local_py/` contiene scripts locales de prueba y depuración, por lo que no forma parte de la clonación.

## Checklist antes del ensayo

Antes de realizar una clonación limpia, comprobé que las credenciales estuvieran protegidas y que los archivos necesarios para reconstruir el entorno estuvieran versionados. Desde la carpeta del repositorio ejecuté:

```powershell
git status --short
git ls-files | Select-String '\.env'
git check-ignore -v .env
Test-Path .\requirements.txt
git ls-files | Select-String '^requirements\.txt$'
```

Los resultados esperados son:

- `git status --short` no muestra cambios inesperados.
- La búsqueda de `.env` muestra solo `.env.example`.
- `git check-ignore` confirma que `.env` está excluido por `.gitignore`.
- `Test-Path` devuelve `True` para `requirements.txt` y Git lo muestra como archivo versionado.

## Ensayo de clonación limpia en Windows

El 23 de octubre de 2026 realicé el ensayo en una carpeta temporal independiente de mi copia de trabajo. Estos son los pasos para repetirlo desde PowerShell.

### 1. Clonar en una carpeta temporal

```powershell
cd $env:TEMP
git clone https://github.com/pzuniga/ProyectoIA_Skillnest.git ProyectoIA_Skillnest_Gate_1_prueba
cd .\ProyectoIA_Skillnest_Gate_1_prueba
```

Comprueba que la copia esté limpia y que los archivos locales no hayan sido descargados:

```powershell
git status --short
Test-Path .env
Test-Path .\venv
Test-Path .\requirements.txt
```

En el ensayo, el estado de Git no mostró cambios; `.env` y `venv/` no existían en el clon; `requirements.txt` sí estaba presente.

### 2. Crear y activar un entorno nuevo

```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
Get-Command python
python --version
```

La ruta mostrada por `Get-Command python` debe estar dentro de la carpeta `venv` del clon. En mi ensayo utilicé Python 3.10.5. Tu versión puede ser distinta.

La primera activación fue bloqueada porque PowerShell tenía deshabilitada la ejecución de scripts. La habilité solo para la sesión actual con `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y la activación se completó. El cambio se pierde al cerrar esa ventana de PowerShell.

### 3. Instalar las dependencias

Con `(venv)` visible en la terminal, ejecuta:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

En mi ensayo, ambas operaciones terminaron correctamente y las dependencias de `requirements.txt` se instalaron en el entorno virtual nuevo.

### 4. Crear `.env` local y comprobar la exclusión

Crea `.env` a partir de la plantilla y agrega tu propia clave de API. No copies ni publiques credenciales en el repositorio:

```powershell
Copy-Item .env.example .env
notepad .env
```

En el Bloc de notas, reemplaza el valor de ejemplo de `GEMINI_API_KEY`, guarda el archivo y cierra el editor. Después confirma que `.env` está ignorado y no aparece como cambio:

```powershell
git check-ignore -v .env
git status --short
```

Durante mi ensayo utilicé mi configuración local de Gemini en la copia temporal. Git confirmó que `.env` estaba ignorado y `git status --short` permaneció vacío.

### 5. Ejecutar una petición real a Gemini

Con el entorno activo y la clave configurada, ejecuta:

```powershell
python .\src\consumir_gemini.py
```

En el ensayo obtuve una respuesta del modelo, sin excepción ni error de autenticación o conexión:

```text
Latencia: 1.86 segundos
Costo de la petición: 0.000070 USD
{'categoria': 'conexion', 'nivel': 1}
```

El costo es la estimación que imprimió el script para esa petición; puede variar en futuras ejecuciones. No compartas la clave de API al registrar o publicar la salida.

### 6. Comprobar el estado final

```powershell
git status --short
git ls-files | Select-String '\.env'
```

En mi ensayo, el estado final de Git siguió limpio y la búsqueda de archivos versionados mostró únicamente `.env.example`.

### Resultado registrado

| Criterio | Resultado del ensayo |
|---|---|
| Clonación desde GitHub | Correcta: 56 objetos recibidos y resolución de deltas completada. |
| Archivos locales al clonar | `.env` y `venv/` no estaban presentes. |
| `requirements.txt` | Presente, versionado y suficiente para instalar las dependencias declaradas. |
| Entorno virtual | Creado y activado con Python 3.10.5. |
| Instalación de dependencias | Completada sin errores. |
| Activación en PowerShell | La primera ejecución fue bloqueada; se resolvió con una política `Bypass` limitada a la sesión actual. |
| Consumo de Gemini | Correcto: el script recibió una respuesta real en 1,86 segundos. |
| Protección de credenciales | `.env` ignorado y no versionado; Git mostró únicamente `.env.example`. |
| Estado final de Git | Limpio. |

## Reglas que sigo durante el programa

- No incluyo contraseñas, claves de API ni tokens en el código o en archivos que subo al repositorio.
- Mantengo un entorno virtual separado para cada proyecto.
- Versiono el trabajo del programa en GitHub y excluyo los archivos locales que contienen secretos.
- Actualizo este README cuando cambian los pasos de instalación, las dependencias o la estructura del proyecto.

## Solución de problemas

- **La terminal no reconoce `git` o `python`:** comprueba que estén instalados y vuelve a abrir la terminal. En macOS usa `python3` para crear el entorno virtual.
- **PowerShell bloquea la activación:** ejecuta `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` en la sesión actual y vuelve a activar el entorno.
- **No aparece `(venv)`:** confirma que estás dentro de la carpeta del proyecto y que ejecutaste el comando correcto para tu sistema.
- **No se encuentra `requirements.txt`:** confirma que estás en la raíz de la copia clonada.
- **Gemini devuelve un error de autenticación:** verifica que `.env` contenga la variable `GEMINI_API_KEY` y que la clave sea válida.
- **La solicitud no se completa:** comprueba tu conexión a internet y vuelve a ejecutar el script. Conserva el código de error para diagnosticar el problema, pero no compartas la clave.

---

**Proyecto:** `ProyectoIA_Skillnest_Gate_1`  
**Etapa:** Gate 1  
**Programa:** Especialización en Desarrollo con IA Generativa (Accenture)
