FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    HF_HOME=/app/.cache/huggingface
COPY synonym-matching/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir torch==2.6.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt
COPY workflow_io.py ./src/workflow_io.py
COPY synonym-matching/src/ ./src/
COPY synonym-matching/schemas/ ./schemas/
COPY synonym-matching/scripts/prepare_model.py ./scripts/prepare_model.py
# Provision the pinned model once; pair processing never downloads resources.
RUN python scripts/prepare_model.py
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
ENTRYPOINT ["python", "/app/src/main.py"]
