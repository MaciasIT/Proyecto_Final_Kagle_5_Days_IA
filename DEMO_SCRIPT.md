# Guía de Grabación para Demo de Kaggle

Sigue estos pasos para grabar un video perfecto de tu agente "Doc Squad AI".

## Preparación
1. Asegúrate de que la aplicación está corriendo: `streamlit run app.py`
2. Abre la aplicación en tu navegador: http://localhost:8501
3. Ten a mano el archivo de audio: `test_audio.mp3` (o el original si prefieres).
4. Prepara tu software de grabación de pantalla (OBS, QuickTime, etc.).

## Guion del Video

### 1. Introducción (0:00 - 0:10)
*   **Acción:** Muestra la pantalla de inicio de "Doc Squad AI".
*   **Narración (Opcional):** "Hola, presento Doc Squad AI, un agente inteligente diseñado para transformar contenido multimedia en documentación técnica automáticamente."

### 2. Configuración (0:10 - 0:20)
*   **Acción:** Abre la barra lateral (Sidebar).
*   **Acción:** Muestra brevemente la configuración de la API Key (si ya está configurada, señala el check verde).
*   **Acción:** Explica brevemente los agentes listados en la barra lateral (IngestAgent, AnalystAgent, TechWriterAgent).

### 3. Carga de Archivo (0:20 - 0:40)
*   **Acción:** Haz clic en "Browse files" y selecciona tu archivo de audio.
*   **Acción:** Mientras se carga, escribe en el campo de contexto:
    > "Este audio explica los 10 pilares del pensamiento estratégico. Enfocarse en los puntos clave para la toma de decisiones."

### 4. Ejecución del Agente (0:40 - 1:30)
*   **Acción:** Haz clic en el botón **"Generar Documentación"**.
*   **Acción:** Observa y señala los logs en tiempo real que aparecen.
    *   Menciona cuando veas "IngestAgent" (Subiendo archivo).
    *   Menciona cuando veas "AnalystAgent" (Analizando hechos).
    *   Menciona cuando veas "TechWriterAgent" (Escribiendo documento).

### 5. Resultado y Cierre (1:30 - 2:00)
*   **Acción:** Cuando aparezca el documento final, haz scroll suavemente hacia abajo para mostrar la estructura (Título, Resumen, Pasos, etc.).
*   **Acción:** Haz clic en el botón **"Descargar Markdown"** para demostrar que funciona.
*   **Narración:** "Como pueden ver, hemos pasado de un archivo de audio a una documentación técnica estructurada en cuestión de minutos. Gracias."

## Consejos Pro
*   Graba en alta resolución (1080p).
*   Limpia tu escritorio de iconos o ventanas innecesarias.
*   Si te equivocas, pausa y retoma, luego puedes editar el video.
