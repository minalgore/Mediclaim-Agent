FROM python:3.8-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

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

RUN python -m pip install --no-cache-dir \
        "pip<25" \
        "setuptools<75" \
        "wheel"

COPY requirements.txt .

RUN python -m pip install --no-cache-dir \
        --prefer-binary \
        -r requirements.txt

COPY . .

# Verify application import inside the Docker image.
RUN PYTHONPATH=/app python -c \
    "from main import app; print('Docker FastAPI import: PASS')"

RUN mkdir -p \
    data/policies \
    data/sample_claims \
    data/medical_documents \
    vectorstore

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]