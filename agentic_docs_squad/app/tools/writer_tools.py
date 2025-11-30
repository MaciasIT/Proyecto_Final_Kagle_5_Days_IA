import os

def save_document_tool(filename: str, content: str) -> str:
    """
    Guarda el contenido de texto en un archivo en el directorio 'output'.

    Args:
        filename: El nombre del archivo a guardar (p. ej., 'mi_documento.md').
        content: El contenido de texto que se escribirá en el archivo.

    Returns:
        Un mensaje de confirmación con la ruta del archivo guardado o un mensaje de error.
    """
    try:
        # Para mantener el proyecto ordenado, guardamos los resultados en un directorio 'output'
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        file_path = os.path.join(output_dir, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        confirmation_message = f"Archivo guardado exitosamente en: {file_path}"
        print(f"[Herramienta de Escritura] {confirmation_message}")
        return confirmation_message
    except Exception as e:
        error_message = f"Error al guardar el archivo '{filename}': {e}"
        print(f"[Herramienta de Escritura] 💥 {error_message}")
        return f"ERROR: {error_message}"
