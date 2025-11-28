# 🤖 Doc Squad AI: Transformando Multimedia en Documentación Técnica con Agentes Inteligentes

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Google ADK](https://img.shields.io/badge/Google-ADK-4285F4.svg)](https://ai.google.dev/adk)
[![Gemini](https://img.shields.io/badge/Gemini-2.5%20Pro%20%26%20Flash-orange.svg)](https://ai.google.dev/gemini-api)
[![Kaggle](https://img.shields.io/badge/Kaggle-Capstone%20Project-blueviolet.svg)](https://www.kaggle.com/competitions/google-gemini-ai-agents-intensive-capstone-project)

**Proyecto Final - Kaggle Agents Intensive Capstone Project**

## 💡 El Problema: La Brecha entre Contenido Multimedia y Documentación Técnica

En el dinámico mundo de la tecnología, la creación de documentación técnica precisa y actualizada a partir de fuentes multimedia (videos de tutoriales, grabaciones de sesiones, audios de conferencias, capturas de pantalla) es un desafío constante. Los ingenieros y equipos de soporte a menudo dedican horas a transcribir, analizar y estructurar manualmente esta información, un proceso que es:

- ⏳ **Lento y Costoso**: Requiere una inversión significativa de tiempo y recursos humanos.
-  prone **Propenso a Errores**: La transcripción y el análisis manual pueden introducir imprecisiones.
- 📉 **Ineficiente**: Retrasa la disponibilidad de información crítica y la escalabilidad del conocimiento.

## 🚀 La Solución: Doc Squad AI - Tu Equipo de Agentes Autónomos

**Doc Squad AI** es un sistema multi-agente inteligente diseñado para cerrar esta brecha. Automatiza la transformación de cualquier contenido multimedia técnico en documentación profesional y estructurada en Markdown, liberando a los equipos para que se centren en tareas de mayor valor.

### 🏗️ Arquitectura "Doc Squad"

Nuestro sistema simula un flujo de trabajo colaborativo con tres agentes especializados, orquestados por el **Google Agent Development Kit (ADK)** y potenciados por los modelos **Gemini 2.5**:

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│  IngestAgent    │ ───▶ │  AnalystAgent    │ ───▶ │  TechWriterAgent    │
│ (El Bibliotecario)│      │ (El Ingeniero)   │      │  (El Redactor)      │
└─────────────────┘      └──────────────────┘      └─────────────────────┘
```

1.  **IngestAgent (El Bibliotecario)**
    *   **Función**: Gestiona la subida y validación de archivos multimedia a la API de Gemini.
    *   **Herramientas**: Utiliza una herramienta personalizada (`ingest_multimedia_tool`) para interactuar con la API de Gemini.
    *   **Salida**: URIs de archivos procesados, listos para análisis.

2.  **AnalystAgent (El Ingeniero)**
    *   **Función**: Analiza el contenido técnico del multimedia procesado.
    *   **Habilidades**: Extrae hechos puros y críticos: comandos ejecutados, mensajes de error, topología de red, configuraciones, etc.
    *   **Salida**: Una lista cronológica y detallada de acciones y datos técnicos.

3.  **TechWriterAgent (El Redactor)**
    *   **Función**: Transforma los hechos crudos en un documento profesional.
    *   **Habilidades**: Aplica formato Markdown estándar, estructura el contenido con títulos, listas y bloques de código, y añade advertencias o notas importantes.
    *   **Salida**: Documentación técnica final en formato Markdown.

## ✨ Características y Beneficios Clave

-   🎥 **Ingesta Multimedia Inteligente**: Procesa videos, audios e imágenes, convirtiendo fuentes no estructuradas en datos analizables.
-   🧠 **Análisis Técnico Profundo**: Extrae automáticamente información crítica, reduciendo el esfuerzo manual y mejorando la precisión.
-   📝 **Documentación Profesional Automatizada**: Genera documentos Markdown bien estructurados y listos para usar, ahorrando tiempo y garantizando la consistencia.
-   🔄 **Pipeline Asíncrono y Eficiente**: Orquestación fluida de agentes para un flujo de trabajo rápido y escalable.
-   🛠️ **Agentes con Herramientas Personalizadas**: Cada agente está equipado con las herramientas necesarias para su rol, maximizando su eficacia.
-   🗣️ **Memoria y Sesiones Persistentes**: Los agentes mantienen el contexto de la conversación y el historial de la sesión, permitiendo interacciones más coherentes y complejas.
-   📊 **Observabilidad Integrada**: Logging detallado para monitorear el progreso del pipeline y facilitar la depuración.
-   🧪 **Evaluación de Agentes**: Un sistema de evaluación automatizado compara la documentación generada con estándares "golden", asegurando la calidad y permitiendo mejoras continuas.

## 🏆 Alineación con el Kaggle Agents Intensive Capstone Project

Doc Squad AI aborda directamente los requisitos clave de la competición:

-   **Sistemas Multi-Agente**: Implementa una arquitectura de tres agentes colaborativos.
-   **Herramientas (Tools)**: Cada agente utiliza herramientas específicas para interactuar con el entorno (ej. `ingest_multimedia_tool`).
-   **Sesiones y Memoria**: Mantiene el estado y el historial de las interacciones a través de sesiones persistentes.
-   **Ingeniería de Contexto**: Los prompts de los agentes están cuidadosamente diseñados para guiar su comportamiento y asegurar resultados óptimos.
-   **Observabilidad**: Incorpora un sistema de logging robusto para el seguimiento del pipeline.
-   **Evaluación de Agentes**: Incluye un script de evaluación que mide la calidad de la documentación generada.
-   **Despliegue**: Ofrece una interfaz Streamlit para una interacción sencilla y un despliegue potencial.

## 🚀 Primeros Pasos

### 1. Clonar el repositorio

```bash
git clone https://github.com/Michel-Macias/Proyecto_Final_Kagle_5_Days_IA.git
cd Proyecto_Final_Kagle_5_Days_IA
```

### 2. Configurar entorno virtual e instalar dependencias

```bash
python3 -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

O usar el script automatizado:

```bash
chmod +x setup_env.sh
./setup_env.sh
```

### 3. Configurar Google API Key

Crea un archivo `.env` en la raíz del proyecto con tu clave API de Google AI Studio:

```bash
echo 'GOOGLE_API_KEY="tu_api_key_aqui"' > .env
```

> ⚠️ **IMPORTANTE**: Nunca compartas tu API key públicamente ni la subas a repositorios.

## 🎯 Uso Detallado

Para una guía completa sobre cómo interactuar con Doc Squad AI, incluyendo la interfaz web, notebooks y scripts de verificación, consulta [USAGE.md](USAGE.md).

## 📁 Estructura del Proyecto

```
Proyecto_Kagle/
├── README.md                          # Este archivo
├── .gitignore                         # Archivos ignorados por git
├── .env                               # API keys (NO incluido en repo)
├── setup_env.sh                       # Script de configuración automática
│
├── app.py                             # Interfaz web con Streamlit
├── project_notebook.ipynb             # Notebook principal (Kaggle/Colab)
├── project_notebook_local.ipynb       # Notebook para entorno local
├── verify_pipeline.py                 # Script de verificación del pipeline
├── evaluate_agent.py                  # Script para la evaluación de agentes
├── list_models.py                     # Utilidad para listar modelos disponibles
│
└── src/                               # Código fuente principal
    └── doc_squad.py                   # Lógica del pipeline de agentes
│
└── test_data/                         # Datos de prueba
    ├── sample_video.mp4               # Video de ejemplo
    ├── sudo_pacman_update.webm        # Video de actualización de paquetes
    ├── test_log.txt                   # Log de prueba
    └── golden_doc.md                  # Documentación "golden" para evaluación
```

## 🛠️ Tecnologías Utilizadas

-   **[Google ADK](https://ai.google.dev/adk)**: Framework de desarrollo de agentes.
-   **[Gemini 2.5 Pro](https://ai.google.dev/gemini-api)**: Modelo de lenguaje avanzado para análisis y redacción.
-   **[Gemini 2.5 Flash](https://ai.google.dev/gemini-api)**: Modelo rápido y eficiente para tareas de ingesta.
-   **[Python 3.8+](https://www.python.org/)**: Lenguaje de programación principal.
-   **[Streamlit](https://streamlit.io/)**: Para la creación de la interfaz web interactiva.
-   **[Jupyter Notebook](https://jupyter.org/)**: Entorno interactivo para desarrollo y demostraciones.
-   **[python-dotenv](https://pypi.org/project/python-dotenv/)**: Gestión segura de variables de entorno.
-   **[nest_asyncio](https://pypi.org/project/nest-asyncio/)**: Para permitir bucles de eventos asíncronos anidados.

## 🔐 Seguridad

-   ✅ El archivo `.env` está incluido en `.gitignore` para proteger tus credenciales.
-   ✅ Las API keys nunca se hardcodean en el código fuente.
-   ✅ Se usa `python-dotenv` para una gestión segura de credenciales.
-   ⚠️ Revoca y regenera tu API key si accidentalmente la expones.

## 🧪 Testing y Evaluación

El proyecto incluye varios mecanismos para asegurar la calidad y el correcto funcionamiento:

1.  **Pipeline Real** (`verify_pipeline.py`): Ejecuta el flujo completo de agentes con datos de prueba reales.
2.  **Evaluación de Agentes** (`evaluate_agent.py`): Compara la documentación generada con una versión "golden" (ideal) utilizando un agente evaluador basado en Gemini, proporcionando una puntuación y feedback detallado.
3.  **Verificación de Sintaxis**: Scripts y herramientas para validar la estructura y el formato del código.

## 📚 Aprendizajes del Proyecto

Este proyecto fue desarrollado como parte del **Kaggle Agents Intensive Capstone Project** y demuestra:

-   ✅ Diseño e implementación de arquitecturas de agentes colaborativos con Google ADK.
-   ✅ Desarrollo y uso de herramientas personalizadas (Custom Tools) para agentes.
-   ✅ Procesamiento avanzado de contenido multimedia con Gemini API.
-   ✅ Orquestación de flujos de trabajo complejos y gestión de estado (sesiones y memoria).
-   ✅ Implementación de observabilidad y evaluación para sistemas de agentes.
-   ✅ Buenas prácticas de desarrollo de software (entornos virtuales, gestión de secretos, logging).
-   ✅ Creación de interfaces interactivas con Streamlit.

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1.  Haz fork del proyecto.
2.  Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`).
3.  Commit tus cambios (`git commit -m 'Add some AmazingFeature'`).
4.  Push a la rama (`git push origin feature/AmazingFeature`).
5.  Abre un Pull Request.

## 📄 Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

## 👤 Autor

**Michel Macías**

-   GitHub: [@Michel-Macias](https://github.com/Michel-Macias)
-   Proyecto: [Proyecto_Final_Kagle_5_Days_IA](https://github.com/Michel-Macias/Proyecto_Final_Kagle_5_Days_IA)

## 🙏 Agradecimientos

-   [Kaggle](https://www.kaggle.com/) por el programa "Agents Intensive Capstone Project".
-   [Google AI](https://ai.google.dev/) por Google ADK y Gemini API.
-   La comunidad de desarrolladores de IA.

---

⭐ Si este proyecto te resultó útil, considera darle una estrella en GitHub!