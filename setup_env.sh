#!/bin/bash

echo "🚀 Iniciando configuración del entorno para Doc Squad..."

# 1. Crear entorno virtual si no existe
if [ ! -d ".venv" ]; then
    echo "📦 Creando entorno virtual (.venv)..."
    python3 -m venv .venv
else
    echo "✅ El entorno virtual ya existe."
fi

# 2. Activar entorno e instalar dependencias
echo "🔌 Activando entorno e instalando librerías..."
source .venv/bin/activate

# Actualizar pip
pip install --upgrade pip

# Instalar dependencias del proyecto
pip install notebook google-adk google-generativeai python-dotenv

# 3. Lanzar Jupyter Notebook
echo "✨ Todo listo. Lanzando Jupyter Notebook..."
echo "⚠️  Recuerda seleccionar el kernel '.venv' si te lo pide, o simplemente abre 'project_notebook_local.ipynb'."
jupyter notebook project_notebook_local.ipynb
