# Guía de Uso — Doc Squad AI v2

Este documento detalla las diferentes formas de interactuar con el sistema **Doc Squad AI v2**.

---

## 🌐 1. Versión en Línea (Live Demo)

Accede directamente desde cualquier navegador sin necesidad de instalar nada:
👉 **[https://doc-squad-ai.streamlit.app/](https://doc-squad-ai.streamlit.app/)**

---

## 🐳 2. Despliegue con Docker (Local o Servidor 24/7)

La forma recomendada para mantener el servicio activo en tu servidor o máquina local con persistencia de datos:

```bash
# 1. Clonar el repositorio
git clone https://github.com/Michel-Macias/Proyecto_Final_Kagle_5_Days_IA.git
cd Proyecto_Final_Kagle_5_Days_IA

# 2. Configurar variables (opcional)
cp .env.example .env

# 3. Iniciar el contenedor en segundo plano
docker compose up -d
```

- La aplicación estará disponible en `http://localhost:8501`.
- Los datos de usuarios e invitaciones se guardan de forma persistente en `./data/doc_squad.db`.

---

## 💻 3. Flujo de Autenticación e Invitaciones

1. **Primer Inicio (Registro del Administrador):**
   - Al abrir la aplicación por primera vez, detectará que no existen cuentas y te solicitará crear la cuenta del **Administrador**.
2. **Generación de Invitaciones Familiares:**
   - Como Administrador, dirígete a la barra lateral a la sección **✉️ Invitaciones Familiares**.
   - Selecciona el tiempo de validez del código (por defecto 72 horas) y pulsa en **"Generar Código"**.
   - Comparte el código con tu familiar o compañero de equipo.
3. **Registro con Invitación:**
   - La persona invitada accede a la URL, va a la pestaña **"Registrarse con Invitación"**, introduce su usuario, contraseña y el código recibido.
   - Una vez registrado, el código queda marcado como utilizado (`used`) y no puede volver a usarse.

---

## 🧠 4. Selección del Motor LLM

En la barra lateral de la aplicación puedes elegir qué proveedor de inferencia utilizar en cualquier momento:

- **SambaNova / Cerebras / Nous:** Modelos de 70B (Llama 3.3, Hermes 3) con inferencia ultrarrápida en nube.
- **FreeLLMAPI:** Conexión local a tu instancia de FreeLLMAPI en `http://127.0.0.1:3001`.
- **Ollama:** Inferencia 100% local y offline en `http://127.0.0.1:11434` (ej. `qwen2.5:1.5b` o `llama3.2:3b`).
- **OpenAI Oficial:** Modelos estándar como `gpt-4o-mini`.

Si el proveedor elegido no tiene su clave definida en el archivo `.env`, puedes introducirla de forma segura directamente en el campo de texto de la barra lateral.

---

## 🎙️ 5. Procesamiento Multimedia y Documentación

1. En la pantalla principal, arrastra y suelta tu archivo:
   - **Vídeos:** `.mp4`, `.webm`, `.mkv`, `.mov`, `.avi`.
   - **Audios:** `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.opus`.
   - **Terminales / Logs:** `.cast` (asciinema), `.log`, `.txt`, `.md`.
2. (Opcional) Introduce contexto o aclaraciones sobre el procedimiento.
3. Pulsa en **"🚀 Generar Documentación"**.
4. Visualiza el progreso de los agentes en tiempo real (`IngestAgent`, `AnalystAgent`, `ValidatorAgent` y `TechWriterAgent`).
5. Lee el Markdown generado y descárgalo con el botón **"📥 Descargar Documentación (Markdown)"**.

---

## 🧪 6. Ejecución de Tests

Para verificar la integridad de todos los módulos del sistema:

```bash
uv run --with-requirements requirements.txt pytest tests/ -v
```
