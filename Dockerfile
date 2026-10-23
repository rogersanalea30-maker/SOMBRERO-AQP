# ==============================================================================
# Dockerfile para Sistema de Facturación Electrónica SUNAT UBL 2.1 (FastAPI)
# ==============================================================================

FROM python:3.12-slim

# Evitar que Python escriba archivos .pyc y habilitar salida en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema requeridas para lxml y criptografía
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente de la aplicación
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY .env.example .env

# Crear directorios de almacenamiento
RUN mkdir -p app/certificates app/storage/xml app/storage/zip app/storage/cdr app/storage/pdf

# Exponer el puerto de FastAPI
EXPOSE 8000

# Comando de inicio del servidor
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
