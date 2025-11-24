# 🤖 Sistema Multi-Agente de Documentación TI con Google ADK

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Google ADK](https://img.shields.io/badge/Google-ADK-4285F4.svg)](https://ai.google.dev/adk)
[![Gemini](https://img.shields.io/badge/Gemini-1.5%20Pro-orange.svg)](https://ai.google.dev/gemini-api)

**Proyecto Final - Kaggle 5 Days of AI**

Sistema inteligente que transforma contenido multimedia (videos, audios, imágenes) en documentación técnica profesional mediante una arquitectura de agentes colaborativos.

## 📋 Descripción

Este proyecto implementa una arquitectura de **Agentes Colaborativos** llamada "Doc Squad" que automatiza la creación de documentación técnica a partir de datos no estructurados. Simula un flujo de trabajo real con tres agentes especializados que trabajan en cadena:

### 🏗️ Arquitectura "Doc Squad"

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│  IngestAgent    │ ───▶ │  AnalystAgent    │ ───▶ │  TechWriterAgent    │
│ (El Bibliotecario)│      │ (El Ingeniero)   │      │  (El Redactor)      │
└─────────────────┘      └──────────────────┘      └─────────────────────┘
```

1. **IngestAgent (El Bibliotecario)**
   - Gestiona la subida y validación de archivos multimedia
   - Utiliza la API de Gemini para procesar archivos
   - Retorna URIs listos para análisis

2. **AnalystAgent (El Ingeniero)**
   - Analiza el contenido técnico del multimedia
   - Extrae hechos puros: comandos, errores, topología de red, configuraciones
   - Genera una lista cronológica de acciones técnicas

3. **TechWriterAgent (El Redactor)**
   - Toma los hechos extraídos y genera documentación profesional
   - Aplica formato Markdown con estructura estándar
   - Añade advertencias, notas y bloques de código

## ✨ Características

- 🎥 **Ingesta Multimedia**: Procesa videos, audios e imágenes
- 🧠 **Análisis Inteligente**: Extracción automática de información técnica
- 📝 **Documentación Profesional**: Genera documentos Markdown estructurados
- 🔄 **Pipeline Asíncrono**: Flujo de trabajo eficiente con Google ADK
- 🛠️ **Herramientas Personalizadas**: Tools específicas para cada agente
- 🧪 **Testing Incluido**: Scripts de verificación del pipeline completo

## 🚀 Requisitos Previos

- **Python 3.8+**
- **Google API Key** (Gemini API)
- Cuenta en [Google AI Studio](https://makersuite.google.com/app/apikey)

## 📦 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/Michel-Macias/Proyecto_Final_Kagle_5_Days_IA.git
cd Proyecto_Final_Kagle_5_Days_IA
```

### 2. Configurar entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install --upgrade pip
pip install notebook google-adk google-generativeai python-dotenv
```

O usar el script automatizado:

```bash
chmod +x setup_env.sh
./setup_env.sh
```

### 4. Configurar API Key

Crea un archivo `.env` en la raíz del proyecto:

```bash
echo 'GOOGLE_API_KEY="tu_api_key_aqui"' > .env
```

> ⚠️ **IMPORTANTE**: Nunca compartas tu API key públicamente ni la subas a repositorios.

## 🎯 Uso

### Opción 1: Jupyter Notebook (Recomendado para Kaggle/Colab)

1. Abre el notebook principal:
   ```bash
   jupyter notebook project_notebook.ipynb
   ```

2. Ejecuta las celdas secuencialmente para ver la demo completa

3. Para uso local con entorno virtual:
   ```bash
   jupyter notebook project_notebook_local.ipynb
   ```

### Opción 2: Script de Verificación

Ejecuta el pipeline completo con datos de prueba reales:

```bash
python verify_pipeline.py
```

Este script:
- Carga un video de ejemplo desde `test_data/`
- Ejecuta los 3 agentes en secuencia
- Muestra el documento final generado

### Opción 3: Uso Programático

```python
import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.adk.agents.llm_agent import Agent

# Configurar API
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Definir agentes (ver project_notebook.ipynb para código completo)
# ...

# Ejecutar pipeline
final_doc = run_documentation_pipeline("ruta/al/video.mp4", "Contexto del tutorial")
print(final_doc)
```

## 📁 Estructura del Proyecto

```
Proyecto_Kagle/
├── README.md                          # Este archivo
├── .gitignore                         # Archivos ignorados por git
├── .env                               # API keys (NO incluido en repo)
├── setup_env.sh                       # Script de configuración automática
│
├── project_notebook.ipynb             # Notebook principal (Kaggle/Colab)
├── project_notebook_local.ipynb       # Notebook para entorno local
├── verify_pipeline.py                 # Script de verificación del pipeline
├── list_models.py                     # Utilidad para listar modelos disponibles
│
└── test_data/                         # Datos de prueba
    ├── sample_video.mp4               # Video de ejemplo
    ├── sudo_pacman_update.webm        # Video de actualización de paquetes
    └── test_log.txt                   # Log de prueba
```

## 🛠️ Tecnologías Utilizadas

- **[Google ADK](https://ai.google.dev/adk)**: Framework de desarrollo de agentes
- **[Gemini 1.5 Pro](https://ai.google.dev/gemini-api)**: Modelo de lenguaje para análisis y redacción
- **[Gemini 1.5 Flash](https://ai.google.dev/gemini-api)**: Modelo rápido para tareas simples
- **[Python 3.8+](https://www.python.org/)**: Lenguaje de programación
- **[Jupyter Notebook](https://jupyter.org/)**: Entorno interactivo
- **[python-dotenv](https://pypi.org/project/python-dotenv/)**: Gestión de variables de entorno

## 🔐 Seguridad

- ✅ El archivo `.env` está incluido en `.gitignore`
- ✅ Las API keys nunca se hardcodean en el código
- ✅ Se usa `python-dotenv` para gestión segura de credenciales
- ⚠️ Revoca y regenera tu API key si accidentalmente la expones

## 🧪 Testing

El proyecto incluye varios niveles de testing:

1. **Demo Simulada** (`project_notebook.ipynb`): Usa un archivo de texto simulando un transcript
2. **Pipeline Real** (`verify_pipeline.py`): Procesa videos reales con la API de Gemini
3. **Verificación de Sintaxis**: Scripts para validar la estructura del notebook

## 📚 Aprendizajes del Proyecto

Este proyecto fue desarrollado como parte del **Kaggle 5 Days of AI** y demuestra:

- ✅ Arquitectura de agentes colaborativos con Google ADK
- ✅ Uso de herramientas personalizadas (Custom Tools)
- ✅ Procesamiento de multimedia con Gemini API
- ✅ Orquestación de flujos de trabajo complejos
- ✅ Buenas prácticas de desarrollo (entornos virtuales, gestión de secretos)
- ✅ Documentación profesional de proyectos de IA

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Haz fork del proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📄 Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

## 👤 Autor

**Michel Macías**

- GitHub: [@Michel-Macias](https://github.com/Michel-Macias)
- Proyecto: [Proyecto_Final_Kagle_5_Days_IA](https://github.com/Michel-Macias/Proyecto_Final_Kagle_5_Days_IA)

## 🙏 Agradecimientos

- [Kaggle](https://www.kaggle.com/) por el programa "5 Days of AI"
- [Google AI](https://ai.google.dev/) por Google ADK y Gemini API
- La comunidad de desarrolladores de IA

---

⭐ Si este proyecto te resultó útil, considera darle una estrella en GitHub!
