FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/app/.cache/huggingface \
    PYTHONPATH=/app/src

# CPU-Ausführung reicht für den Prototyp; keine CUDA-Pakete installieren.
COPY requirements.txt ./
RUN pip install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        https://github.com/explosion/spacy-models/releases/download/de_core_news_sm-3.8.0/de_core_news_sm-3.8.0-py3-none-any.whl \
        https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

COPY src/ ./src/
COPY schemas/ ./schemas/
COPY scripts/download_models.py scripts/download_lexicons.py ./scripts/

# Ressourcen gehören ins Image und bleiben über Containerstarts hinweg verfügbar.
RUN python scripts/download_models.py \
    && python scripts/download_lexicons.py

# Matching verwendet ausschließlich die beim Build vorbereiteten Modelle.
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

ENTRYPOINT ["python", "/app/src/main.py"]
