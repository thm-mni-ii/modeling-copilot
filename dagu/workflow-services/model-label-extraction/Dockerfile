FROM python:3.12-alpine
WORKDIR /app
COPY workflow_io.py ./src/workflow_io.py
COPY model-label-extraction/src/ ./src/
COPY workflow_server.py ./workflow_server.py
ENTRYPOINT ["python", "/app/src/main.py"]
