FROM python:3.12-alpine
WORKDIR /app
COPY workflow_io.py ./src/workflow_io.py
COPY workflow-data/src/ ./src/
COPY workflow_server.py ./workflow_server.py
ENTRYPOINT ["python", "/app/src/main.py"]
