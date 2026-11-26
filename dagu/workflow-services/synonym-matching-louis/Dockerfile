FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src \
    HF_HOME=/app/.cache/huggingface TOKENIZERS_PARALLELISM=false

COPY requirements.txt ./
RUN pip install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY schemas/ ./schemas/
COPY scripts/ ./scripts/
RUN python scripts/download_models.py && python scripts/download_lexicons.py

ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
ENTRYPOINT ["python", "/app/src/main.py"]
