# ── Dockerfile ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="CryptoAnalytics"
LABEL description="Real-Time Crypto Analytics Platform"

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p logs raw_data data

# Default: run ETL pipeline
CMD ["python", "etl_pipeline.py"]
