# Einfaches API-Image: Python + Abhängigkeiten + Quellcode
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["sh", "-ec", "python -m modeling_api.db.migrations --apply && exec uvicorn modeling_api.main:app --host 0.0.0.0 --port 8000"]
