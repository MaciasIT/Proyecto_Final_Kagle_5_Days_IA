import os
import google.generativeai as genai
from dotenv import load_dotenv

def configure_environment():
    """
    Loads environment variables from a .env file and configures the a
    API key.
    """
    load_dotenv()
    
    google_api_key = os.getenv("GOOGLE_API_KEY")
    
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables or .env file.")
        
    genai.configure(api_key=google_api_key)
    print(f"API Key configured successfully (termina en: ...{google_api_key[-4:]}).")

