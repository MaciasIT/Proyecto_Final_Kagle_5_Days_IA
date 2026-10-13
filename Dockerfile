FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Dependencias de sistema: ffmpeg (extracción de frames y timestamps), bash, curl para healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    bash \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalación de paquetes Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia del código fuente
COPY . .

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
