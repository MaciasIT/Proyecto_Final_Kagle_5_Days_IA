import sys
import os
sys.path.append(os.getcwd())
try:
    from src.doc_squad import run_documentation_pipeline
    print("Import successful")
except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
