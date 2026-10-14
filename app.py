"""
app.py — Interfaz Streamlit para Doc Squad AI v2.

Incluye:
  1. Autenticación de usuarios por invitación (SQLite + bcrypt).
  2. Panel de administración para generación de códigos de invitación de un solo uso.
  3. Selector de motor LLM agnóstico (SambaNova, Cerebras, Nous, FreeLLMAPI, Ollama, OpenAI).
  4. Pipeline multi-agente de documentación técnica sin dependencias de Google.
"""

from __future__ import annotations

import os
import tempfile
import streamlit as st
from dotenv import load_dotenv

from src.auth.db import init_db
from src.auth.service import (
    create_invitation,
    is_admin,
    list_invitations,
    login_user,
    register_user,
    user_count,
)
from src.doc_squad import run_documentation_pipeline
from src.llm.client import AgnosticLLMClient, resolve_provider_config

load_dotenv()

# Inicializar tablas de SQLite si no existen
init_db()

# Configuración de página
st.set_page_config(
    page_title="Doc Squad AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.3rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .auth-card {
        background-color: #f8f9fa;
        padding: 2rem;
        border-radius: 0.8rem;
        border: 1px solid #e0e0e0;
        max-width: 500px;
        margin: auto;
    }
    .stButton>button {
        border-radius: 0.4rem;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# GESTIÓN DE SESIÓN Y AUTENTICACIÓN
# ==============================================================================

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "username" not in st.session_state:
    st.session_state["username"] = None
if "role" not in st.session_state:
    st.session_state["role"] = None


def render_auth_view():
    """Renderiza la vista de autenticación (Login / Registro con Invitación)."""
    st.markdown('<h1 class="main-header">🤖 Doc Squad AI</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Acceso restringido — Inicia sesión o regístrate con tu invitación.</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        total_users = user_count()

        if total_users == 0:
            st.warning("👑 **Primer inicio detectado**: No hay ningún usuario registrado. La primera cuenta que crees será el **Administrador** del sistema.")
            with st.form("admin_register_form"):
                admin_user = st.text_input("Usuario Administrador", placeholder="ej. michel")
                admin_pass = st.text_input("Contraseña", type="password")
                admin_pass_confirm = st.text_input("Confirmar Contraseña", type="password")
                submit_admin = st.form_submit_button("Crear Administrador", use_container_width=True)

                if submit_admin:
                    if not admin_user or not admin_pass:
                        st.error("Por favor, introduce usuario y contraseña.")
                    elif admin_pass != admin_pass_confirm:
                        st.error("Las contraseñas no coinciden.")
                    else:
                        try:
                            user_data = register_user(admin_user.strip(), admin_pass)
                            st.session_state["authenticated"] = True
                            st.session_state["username"] = user_data["username"]
                            st.session_state["role"] = user_data["role"]
                            st.success("¡Administrador registrado exitosamente!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al registrar: {e}")
            return

        # Pestañas Login y Registro con Invitación
        tab_login, tab_register = st.tabs(["🔑 Iniciar Sesión", "✉️ Registrarse con Invitación"])

        with tab_login:
            with st.form("login_form"):
                login_username = st.text_input("Usuario")
                login_password = st.text_input("Contraseña", type="password")
                submit_login = st.form_submit_button("Entrar", use_container_width=True)

                if submit_login:
                    user_info = login_user(login_username.strip(), login_password)
                    if user_info:
                        st.session_state["authenticated"] = True
                        st.session_state["username"] = user_info["username"]
                        st.session_state["role"] = user_info["role"]
                        st.success(f"Bienvenido, {user_info['username']}!")
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas o usuario no encontrado.")

        with tab_register:
            with st.form("register_form"):
                reg_username = st.text_input("Nombre de Usuario deseado")
                reg_password = st.text_input("Contraseña", type="password")
                reg_code = st.text_input("Código de Invitación", placeholder="Pega aquí el código que te enviaron")
                submit_register = st.form_submit_button("Registrarse", use_container_width=True)

                if submit_register:
                    if not reg_username or not reg_password or not reg_code:
                        st.error("Todos los campos son obligatorios.")
                    else:
                        try:
                            new_user = register_user(reg_username.strip(), reg_password, reg_code.strip())
                            st.success("¡Cuenta creada correctamente! Ahora puedes iniciar sesión.")
                        except Exception as e:
                            st.error(f"No se pudo registrar: {e}")


if not st.session_state["authenticated"]:
    render_auth_view()
    st.stop()


# ==============================================================================
# VISTA PRINCIPAL (USUARIO AUTENTICADO)
# ==============================================================================

current_user = st.session_state["username"]
current_role = st.session_state["role"]

# --- SIDEBAR ---
with st.sidebar:
    st.markdown(f"### 👤 {current_user}")
    role_badge = "🛡️ **Administrador**" if current_role == "admin" else "👥 **Invitado / Familia**"
    st.markdown(role_badge)

    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.session_state["role"] = None
        st.rerun()

    st.markdown("---")

    # PANEL DE ADMINISTRACIÓN DE INVITACIONES
    if current_role == "admin":
        st.markdown("### ✉️ Invitaciones Familiares")
        with st.expander("Generar nueva invitación", expanded=False):
            exp_hours = st.slider("Validez (horas)", min_value=12, max_value=168, value=72, step=12)
            if st.button("Generar Código", use_container_width=True):
                try:
                    code = create_invitation(created_by=current_user, role="user", expires_hours=exp_hours)
                    st.success("¡Código generado! Cópialo:")
                    st.code(code, language="text")
                except Exception as e:
                    st.error(f"Error: {e}")

        with st.expander("Ver invitaciones emitidas", expanded=False):
            invs = list_invitations(created_by=current_user)
            if invs:
                for inv in invs[:8]:
                    status_icon = "🟢" if inv["status"] == "active" else ("🔴" if inv["status"] == "used" else "⚪")
                    st.caption(f"{status_icon} `{inv['code'][:8]}...` | Estado: {inv['status']} | Usado por: {inv['used_by'] or 'Nadie'}")
            else:
                st.caption("No hay invitaciones creadas aún.")

        st.markdown("---")

    # CONFIGURACIÓN DEL MOTOR LLM
    st.markdown("### 🧠 Motor LLM Agnóstico")
    provider_options = {
        "SambaNova (Llama 3.3 70B Cloud)": "sambanova",
        "Cerebras (Llama 3.3 70B Cloud)": "cerebras",
        "Nous Research (Hermes 3 Cloud)": "nous",
        "FreeLLMAPI (Local:3001)": "freellmapi",
        "Ollama (Local:11434)": "ollama",
        "OpenAI Oficial": "openai",
    }
    selected_label = st.selectbox(
        "Proveedor LLM activo",
        list(provider_options.keys()),
        index=0,
    )
    provider_key = provider_options[selected_label]

    # Resolver configuración y comprobar API key
    try:
        llm_cfg = resolve_provider_config(provider_key, require_api_key=False)
    except Exception:
        llm_cfg = ProviderConfig(name=provider_key, base_url="https://api.openai.com/v1", api_key="", model="default")

    custom_api_key = None
    if not llm_cfg.api_key or llm_cfg.api_key == "sk-dummy-key":
        custom_api_key = st.text_input(
            f"API Key para {provider_key.capitalize()}",
            type="password",
            help="Introduce tu API key o configúrala en .env / Secrets de Streamlit",
            key=f"api_key_input_{provider_key}",
        )
        if custom_api_key:
            llm_cfg.api_key = custom_api_key.strip()

    # Instanciar cliente LLM para la sesión si la clave está disponible
    if not llm_cfg.api_key or llm_cfg.api_key == "sk-dummy-key":
        st.warning(f"⚠️ Introduce tu API Key de {provider_key.capitalize()} en el campo superior.")
        llm_client = None
    else:
        llm_client = AgnosticLLMClient(config=llm_cfg)
        st.success(f"✅ Conectado a **{provider_key.upper()}** (`{llm_cfg.model}`)")

    st.markdown("---")
    st.markdown("### 🎙️ Audio STT Local")
    st.caption("Faster-Whisper (int8 en CPU i5-10400) activo.")


# --- CONTENIDO PRINCIPAL ---
st.markdown('<h1 class="main-header">🤖 Doc Squad AI</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Documentación técnica automatizada a partir de grabaciones, vídeos, audios y terminales.</p>', unsafe_allow_html=True)

col_input, col_output = st.columns([1, 1])

with col_input:
    st.markdown("### 1. Selecciona el recurso")
    uploaded_file = st.file_uploader(
        "Sube un archivo técnico",
        type=['mp4', 'webm', 'mp3', 'wav', 'cast', 'txt', 'log', 'md'],
        help="Soporta vídeos, pistas de audio, sesiones asciinema y logs de terminal.",
    )

    context = st.text_area(
        "Contexto adicional u objetivo (Opcional)",
        placeholder="Ej: Tutorial de despliegue de PostgreSQL en Debian 12...",
        height=100,
    )

    generate_btn = st.button("🚀 Generar Documentación", type="primary", disabled=not uploaded_file, use_container_width=True)

with col_output:
    st.markdown("### 2. Documentación Generada")
    output_container = st.empty()

    if generate_btn and uploaded_file:
        if not llm_client:
            st.error("⚠️ Configura la API Key del proveedor en la barra lateral antes de continuar.")
            st.stop()

        suffix = f".{uploaded_file.name.split('.')[-1]}"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        try:
            status_container = st.container()

            def update_ui_status(msg: str):
                with status_container:
                    if "IngestAgent" in msg:
                        st.info(msg, icon="📥")
                    elif "AnalystAgent" in msg:
                        st.info(msg, icon="🧠")
                    elif "ValidatorAgent" in msg and "🔁" in msg:
                        st.warning(msg, icon="🔍")
                    elif "ValidatorAgent" in msg:
                        st.info(msg, icon="🔍")
                    elif "TechWriterAgent" in msg:
                        st.info(msg, icon="✍️")
                    elif "✅" in msg:
                        st.success(msg)
                    else:
                        st.write(msg)

            with st.spinner("El Doc Squad está procesando el archivo con el modelo agnóstico..."):
                final_doc = run_documentation_pipeline(
                    file_path=tmp_path,
                    request_context=context,
                    status_callback=update_ui_status,
                    llm_client=llm_client,
                )

            output_container.markdown(final_doc)

            st.download_button(
                label="📥 Descargar Documentación (Markdown)",
                data=final_doc,
                file_name=f"docs_{uploaded_file.name.split('.')[0]}.md",
                mime="text/markdown",
                use_container_width=True,
            )

        except Exception as e:
            st.error(f"Ocurrió un error en el pipeline: {str(e)}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    elif not uploaded_file:
        output_container.info("👈 Sube un archivo para comenzar la documentación.")
