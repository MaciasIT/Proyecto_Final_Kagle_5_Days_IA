import streamlit as st
import os
import tempfile
from dotenv import load_dotenv
from src.doc_squad import run_documentation_pipeline
import google.generativeai as genai

# Configuración de la página
st.set_page_config(
    page_title="Doc Squad AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #4285F4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #4285F4;
        color: white;
    }
    .status-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f0f2f6;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://www.gstatic.com/lamda/images/gemini_sparkle_v002_d4735304ff6292a690345.svg", width=50)
    st.title("Configuración")
    
    # API Key management
    load_dotenv()
    env_api_key = os.getenv("GOOGLE_API_KEY")
    
    # Prioridad: 1. Input del usuario (Session State), 2. Variable de entorno
    if "user_api_key" not in st.session_state:
        st.session_state.user_api_key = None

    if not env_api_key:
        input_key = st.text_input("Google API Key", type="password", help="Introduce tu API Key de Google AI Studio")
        if input_key:
            st.session_state.user_api_key = input_key
            st.success("API Key configurada para esta sesión!")
    else:
        st.success("✅ API Key detectada en el servidor")
        st.session_state.user_api_key = env_api_key

    active_api_key = st.session_state.user_api_key

    st.markdown("---")
    st.markdown("### 🤖 Doc Squad")
    st.markdown("- **IngestAgent**: Procesa multimedia")
    st.markdown("- **AnalystAgent**: Extrae datos técnicos")
    st.markdown("- **TechWriterAgent**: Escribe documentación")
    
    st.markdown("---")
    st.markdown("Created by [Michel Macias](https://github.com/Michel-Macias)")

# Main Content
st.markdown('<h1 class="main-header">🤖 Doc Squad AI</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Transforma videos y audios técnicos en documentación profesional automáticamente.</p>', unsafe_allow_html=True)

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### 1. Sube tu archivo")
    uploaded_file = st.file_uploader("Elige un archivo multimedia o de texto", type=['mp4', 'webm', 'mp3', 'wav', 'png', 'jpg', 'pdf', 'txt'])
    
    context = st.text_area("Contexto adicional (Opcional)", 
                          placeholder="Ej: Este es un tutorial sobre cómo instalar Apache en Ubuntu...",
                          height=100)

    generate_btn = st.button("Generar Documentación", type="primary", disabled=not uploaded_file)

with col2:
    st.markdown("### 2. Resultado")
    output_container = st.empty()
    
    if generate_btn and uploaded_file:
        if not active_api_key:
            st.error("⚠️ Por favor configura tu Google API Key en la barra lateral.")
        else:
            # Guardar archivo temporalmente
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = tmp_file.name

            try:
                # Contenedor para logs en tiempo real
                status_container = st.container()
                
                def update_ui_status(msg):
                    with status_container:
                        if "IngestAgent" in msg:
                            st.info(msg, icon="📥")
                        elif "AnalystAgent" in msg:
                            st.info(msg, icon="🧠")
                        elif "TechWriterAgent" in msg:
                            st.info(msg, icon="✍️")
                        elif "✅" in msg:
                            st.success(msg)
                        else:
                            st.write(msg)

                with st.spinner('El Doc Squad está trabajando... Esto puede tardar unos minutos.'):
                    final_doc = run_documentation_pipeline(tmp_path, context, api_key=active_api_key, status_callback=update_ui_status)
                
                # Mostrar resultado final (Seguro: sin unsafe_allow_html para el contenido de la IA)
                output_container.markdown(final_doc)
                
                # Botón de descarga
                st.download_button(
                    label="Descargar Markdown",
                    data=final_doc,
                    file_name="documentacion_generada.md",
                    mime="text/markdown"
                )
                
            except Exception as e:
                # Sanitizar el mensaje de error antes de mostrarlo
                st.error(f"Ocurrió un error: {str(e).replace('<', '&lt;')}")
            finally:
                # Limpiar archivo temporal
                if 'tmp_path' in locals() and os.path.exists(tmp_path):
                    os.remove(tmp_path)

    elif not uploaded_file:
        output_container.info("👈 Sube un archivo para comenzar.")
