import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ No se encontró GOOGLE_API_KEY")
    exit(1)

genai.configure(api_key=api_key)

print("🧪 Probando conexión básica con Gemini...")

try:
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content("Di 'Hola Mundo' si funcionas.")
    print(f"✅ Respuesta recibida: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")
