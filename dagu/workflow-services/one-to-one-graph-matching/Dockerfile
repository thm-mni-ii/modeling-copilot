FROM python:3.12-alpine
WORKDIR /app
COPY workflow_io.py ./src/workflow_io.py
COPY one-to-one-graph-matching/src/ ./src/
COPY workflow_server.py ./workflow_server.py
ENTRYPOINT ["python", "/app/src/main.py"]
