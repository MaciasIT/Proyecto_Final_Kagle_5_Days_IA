import os
from dotenv import load_dotenv
from src.doc_squad import run_documentation_pipeline

# --- CONFIGURACIÓN ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

def verify_pipeline():
    """
    Ejecuta el pipeline de documentación completo con un archivo de prueba
    y verifica que la salida y los logs se generen correctamente.
    """
    if not GOOGLE_API_KEY:
        print("SKIPPING TEST: No se encontró la GOOGLE_API_KEY en el entorno o en el archivo .env.")
        return

    print("--- INICIANDO TEST DEL PIPELINE DE DOCUMENTACIÓN ---")
    
    # Usar un archivo de prueba del repositorio
    test_file = "test_data/sample_video.mp4"
    context = "Este es un video de demostración sobre cómo usar el comando 'ls' en un terminal Linux."
    
    if not os.path.exists(test_file):
        print(f"ERROR: El archivo de prueba no se encuentra en {test_file}")
        return
        
    print(f"Archivo de prueba: {test_file}")
    print(f"Contexto: {context}")
    print("-" * 20)

    try:
        # Ejecutar el pipeline principal
        final_doc = run_documentation_pipeline(
            file_path=test_file,
            request_context=context,
            status_callback=None  # Usaremos el logger por defecto
        )
        
        print("\n--- DOCUMENTO FINAL GENERADO ---")
        print(final_doc)
        print("-" * 20)

        # Verificar la creación del log
        log_file = "doc_squad.log"
        if os.path.exists(log_file):
            print(f"✅ ÉXITO: El archivo de log '{log_file}' se ha creado correctamente.")
            with open(log_file, 'r') as f:
                log_content = f.read()
                if "Pipeline finalizado con éxito" in log_content:
                    print("✅ ÉXITO: El log contiene el mensaje de finalización del pipeline.")
                else:
                    print("⚠️ ADVERTENCIA: El log no contiene el mensaje de finalización esperado.")
        else:
            print("❌ ERROR: No se ha encontrado el archivo de log 'doc_squad.log'.")

    except Exception as e:
        print(f"❌ ERROR: El pipeline ha fallado con una excepción: {e}")

if __name__ == "__main__":
    verify_pipeline()