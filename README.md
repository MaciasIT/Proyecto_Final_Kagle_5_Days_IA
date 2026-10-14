# 🤖 Doc Squad AI — Sistema Multi-Agente de Documentación Técnica

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B.svg)](https://streamlit.io)
[![OpenAI Compatible](https://img.shields.io/badge/LLM-Agnostic%20(OpenAI%20API)-green.svg)](https://platform.openai.com)
[![faster--whisper](https://img.shields.io/badge/STT-faster--whisper%20(int8)-purple.svg)](https://github.com/SYSTRAN/faster-whisper)
[![Docker](https://img.shields.io/badge/Docker-compose-2496ED.svg)](https://www.docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **🔴 LIVE DEMO:** [https://doc-squad-ai.streamlit.app/](https://doc-squad-ai.streamlit.app/)

Sistema inteligente que transforma contenido multimedia técnico (vídeos, audios, sesiones asciinema y logs) en documentación técnica estructurada y profesional mediante una arquitectura de agentes colaborativos. 

Originalmente desarrollado como proyecto para **Kaggle 5 Days of AI**, evolucionado a **Doc Squad v2** con arquitectura desacoplada de APIs propietarias, motor LLM agnóstico, transcripción local optimizada para CPU y control de acceso multiusuario por invitación.

---

## 📋 Arquitectura "Doc Squad v2"

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
│  IngestAgent    │ ───▶ │  AnalystAgent    │ ───▶ │  ValidatorAgent     │ ───▶ │  TechWriterAgent    │
│ (El Bibliotecario)│     │ (El Ingeniero)   │ ─┐   │  (El Crítico)       │      │  (El Redactor)      │
└─────────────────┘      └──────────────────┘  │   └─────────────────────┘      └─────────────────────┘
         │                        │            │            ▲  │                           │
  faster-whisper local      Inferencia LLM     └────────────┘  └─ Bucle de refinamiento    Markdown técnico
  (CPU int8 + ffmpeg)       (SambaNova /                      (sintaxis + critic)         estructurado
                            Cerebras / Nous /
                            FreeLLMAPI / Ollama)
```

1. **IngestAgent (El Bibliotecario)**
   - Resuelve fuentes multimedia: vídeos (.mp4, .webm), audios (.mp3, .wav), terminales (.cast de asciinema) y logs.
   - Transcribe y ancla marcas temporales `[MM:SS]` localmente mediante **`faster-whisper`** (cuantización `int8` optimizada para CPU).
2. **AnalystAgent (El Ingeniero)**
   - Extrae hechos técnicos precisos: comandos exactos, flags, parámetros, errores, configuraciones de red y paquetes.
3. **ValidatorAgent (El Crítico)**
   - Comprobación sintáctica determinista de comandos (`bash`, `docker`, `python`) con `src.validator`.
   - Critic LLM para coherencia entre comandos y distribución/sistema operativo.
   - Bucle de refinamiento automático con el AnalystAgent ante inconsistencias.
4. **TechWriterAgent (El Redactor)**
   - Genera el documento final en Markdown con estructura profesional (Resumen Ejecutivo, Prerrequisitos, Paso a Paso, Solución de Problemas y Avisos).

---

## ✨ Características Destacadas

- 🌐 **Despliegue Online & Acceso Seguro**: Disponible en [doc-squad-ai.streamlit.app](https://doc-squad-ai.streamlit.app/).
- 🧠 **Motor LLM Agnóstico**: Compatible con el estándar OpenAI Chat Completions. Conmuta en caliente entre:
  - **SambaNova** (Llama 3.3 70B ultra-rápido en Cloud).
  - **Cerebras** (Llama 3.3 70B ultra-rápido en Cloud).
  - **Nous Research** (Hermes 3 Cloud).
  - **FreeLLMAPI** (Local en `http://127.0.0.1:3001`).
  - **Ollama** (Local en `http://127.0.0.1:11434`, ej. `qwen2.5` o `llama3.2`).
  - **OpenAI** (`gpt-4o-mini`).
- 🎙️ **Audio STT Local**: Transcripción offline con `faster-whisper` (modelo `base` en CPU Intel i5-10400 en ~0.5s).
- 🔐 **Autenticación por Invitación**: Base de datos SQLite persistente (`doc_squad.db`) con contraseñas `bcrypt`. El primer usuario registrado es el **Administrador**, con capacidad de generar invitaciones de un solo uso con expiración configurada para familiares o colaboradores.
- 🐳 **Docker Ready**: Empaquetado completo con `Dockerfile` y `docker-compose.yml`, con volumen persistente para datos (`./data:/app/data`).
- 🧪 **135 Tests Unitarios**: Suite de pruebas integral cubriendo el pipeline completo, cliente LLM, auth, grounding y transcripción.

---

## 🚀 Inicio Rápido

### Opción 1: Probar en Línea (Sin Instalación)

Accede directamente a la aplicación desplegada:
👉 **[https://doc-squad-ai.streamlit.app/](https://doc-squad-ai.streamlit.app/)**

### Opción 2: Despliegue con Docker (Recomendado para Servidor / 24/7)

```bash
# 1. Clonar el repositorio
git clone https://github.com/Michel-Macias/Proyecto_Final_Kagle_5_Days_IA.git
cd Proyecto_Final_Kagle_5_Days_IA

# 2. Configurar variables de entorno (opcional si usas proveedores locales)
cp .env.example .env

# 3. Levantar con Docker Compose
docker compose up -d
```
Abre en tu navegador `http://localhost:8501`. La base de datos de usuarios e invitaciones se guardará de forma persistente en `./data`.

### Opción 3: Ejecución Local en Python

```bash
# 1. Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Lanzar Streamlit
streamlit run app.py
```

---

## ⚙️ Configuración (.env)

Copia `.env.example` a `.env` y configura tus proveedores preferidos:

```env
# Proveedor activo: sambanova, cerebras, nous, freellmapi, ollama, openai
LLM_PROVIDER=sambanova

# Claves de proveedores (configura la que uses)
SAMBANOVA_API_KEY=tu_clave_aqui
CEREBRAS_API_KEY=tu_clave_aqui
NOUS_API_KEY=tu_clave_aqui
OPENAI_API_KEY=tu_clave_aqui

# Modelo de transcripción local (tiny, base, small, medium)
WHISPER_MODEL=base

# Directorio de persistencia SQLite
DATA_DIR=./data
```

---

## 🧪 Testing y Calidad

El proyecto cuenta con una cobertura integral de 135 tests sin dependencias externas obligatorias:

```bash
uv run --with-requirements requirements.txt pytest tests/ -v
```

```text
============================= 135 passed in 7.21s ==============================
```

---

## 📁 Estructura del Repositorio

```
├── app.py                             # Interfaz web Streamlit con Auth y Selector LLM
├── Dockerfile                         # Imagen Docker productiva con ffmpeg y libgomp1
├── docker-compose.yml                 # Despliegue con volumen persistente ./data
├── requirements.txt                   # Dependencias de producción
├── .env.example                       # Plantilla de variables de entorno
│
├── src/                               # Código fuente
│   ├── audio/                         # Transcripción local con faster-whisper y ffmpeg
│   ├── auth/                          # Sistema SQLite + bcrypt + invitaciones
│   ├── llm/                           # AgnosticLLMClient multi-proveedor (OpenAI API)
│   ├── video_grounding/               # AudioVideoGrounder, FrameExtractor y schemas
│   ├── doc_squad.py                   # Orquestación del pipeline de agentes
│   ├── validator.py                   # Validador determinista de sintaxis
│   └── contracts.py                   # Modelos de datos Pydantic v2
│
├── tests/                             # Suite completa de pruebas unitarias
└── test_data/                         # Vídeos, grabaciones y logs de prueba
```

---

## 📄 Licencia

Este proyecto está bajo la licencia MIT.

## 👤 Autor

**Michel Macías**
- GitHub: [@Michel-Macias](https://github.com/Michel-Macias)
- Portfolio: [MaciasIT](https://MaciasIT.github.io/Portfolio-Ciberseguridad)
