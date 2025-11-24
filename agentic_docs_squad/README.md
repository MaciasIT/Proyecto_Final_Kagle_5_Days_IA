# Agentic Docs Squad

Este proyecto es una refactorización del cuaderno de Jupyter original a una aplicación de servicio web completa, utilizando FastAPI y el framework `google-adk`.

El sistema utiliza una arquitectura de agentes especializados, gestionados por un orquestador, para analizar archivos multimedia y generar documentación técnica de forma automática.

## Arquitectura

-   **Orquestador (`app/orchestrator.py`):** Una clase principal que gestiona el flujo de trabajo. No es un agente, sino un director que invoca a los agentes especializados en orden.
-   **Agentes Especializados (`app/agents/`):
    -   `IngestAgent`: Responsable de tomar una ruta de archivo local y subirla a la API de Gemini para su procesamiento.
    -   `AnalystAgent`: Analiza el contenido del archivo (una vez procesado por la API) para extraer hechos técnicos clave.
    -   `TechWriterAgent`: Toma los hechos técnicos y los convierte en un documento Markdown bien estructurado.
-   **Herramientas (`app/tools/`):
    -   `file_tools.py`: Contiene la lógica para interactuar con la API de subida de archivos de Gemini.
-   **API (`app/main.py`:
    -   Una API basada en FastAPI que expone el pipeline de documentación a través de un endpoint HTTP.

## Requisitos

-   Python 3.10+
-   Una clave de API de Google (para Gemini).

## Configuración y Ejecución

1.  **Clonar el proyecto y navegar al directorio:**
    ```bash
    cd agentic_docs_squad
    ```

2.  **Crear un entorno virtual:**
    ```bash
    python3 -m venv .venv
    ```

3.  **Activar el entorno virtual:**
    -   En Linux/macOS:
        ```bash
        source .venv/bin/activate
        ```
    -   En Windows:
        ```bash
        .venv\Scripts\activate
        ```

4.  **Instalar las dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configurar la API Key:**
    -   Renombra el archivo `.env.example` a `.env`.
    -   Abre el archivo `.env` y reemplaza `YOUR_API_KEY_HERE` con tu clave de API de Google real.

6.  **Ejecutar la aplicación:**
    ```bash
    python -m app.main
    ```
    El servidor se iniciará y estará disponible en `http://localhost:8000`.

## Cómo Usar la API

Puedes interactuar con la API usando herramientas como `curl` o cualquier cliente HTTP.

-   **Endpoint:** `POST /document/run`
-   **Payload (JSON):**
    ```json
    {
      "user_prompt": "Genera la documentación para el archivo /ruta/completa/a/tu/video.mp4",
      "user_context": "Este es un tutorial sobre cómo instalar un servidor web."
    }
    ```
-   **Respuesta:**
    ```json
    {
      "document": "# Título del Documento\n\n## Resumen\n\n..."
    }
    ```

### Ejemplo con `curl`:

```bash
curl -X POST "http://localhost:8000/document/run" \
-H "Content-Type: application/json" \
-d 
  {
    "user_prompt": "Por favor, crea la documentación para el archivo que se encuentra en ./test_data/sample_video.mp4",
    "user_context": "Es un video de demostración sobre comandos básicos de sistema."
  }
```

**Nota:** Asegúrate de que la ruta del archivo en el `user_prompt` sea accesible desde la máquina donde se ejecuta el servidor.

## Ejecutar las Pruebas

Para verificar que todo está configurado correctamente, puedes ejecutar la suite de pruebas:

```bash
# Asegúrate de que tu entorno virtual esté activado
pip install pytest pytest-asyncio
pytest
```
