FROM python:3.8-slim

# Prevent Python from writing .pyc files
# and ensure logs are immediately visible.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ------------------------------------------------------------
# System dependencies
# ------------------------------------------------------------
# Tesseract is required for OCR.
# Build tools are included because some Python packages may
# need to build native extensions during installation.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libgl1 \
        libglib2.0-0 \
        build-essential \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Python packaging tools
# ------------------------------------------------------------
RUN python -m pip install --no-cache-dir \
        "pip<25" \
        "setuptools<75" \
        "wheel"

# ------------------------------------------------------------
# Install Python dependencies
# ------------------------------------------------------------
COPY requirements.txt .

RUN python -m pip install --no-cache-dir \
        --prefer-binary \
        -r requirements.txt

# ------------------------------------------------------------
# Copy application
# ------------------------------------------------------------
COPY . .

# ------------------------------------------------------------
# Required runtime directories
# ------------------------------------------------------------
RUN mkdir -p \
    data/policies \
    data/sample_claims \
    data/medical_documents \
    vectorstore

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]