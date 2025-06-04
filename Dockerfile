FROM python:3.11-slim

# Arbeitsverzeichnis
WORKDIR /app

# Abhängigkeiten
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Restliche Dateien reinlegen
COPY . .

# Standard-Entrypoint (änderbar über Compose)
CMD ["python", "main.py"]