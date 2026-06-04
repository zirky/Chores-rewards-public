FROM python:3.11-slim

WORKDIR /app

# Závislosti + sqlite3 CLI pro přímý přístup k DB
RUN apt-get update && apt-get install -y --no-install-recommends sqlite3 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Zdrojový kód
COPY app/ ./app/
COPY sql/ ./sql/

# Adresář pro SQLite databázi
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
