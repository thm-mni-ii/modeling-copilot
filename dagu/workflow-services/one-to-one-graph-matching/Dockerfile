FROM python:3.12-alpine
WORKDIR /app
COPY workflow_io.py ./src/workflow_io.py
COPY one-to-one-graph-matching/src/ ./src/
ENTRYPOINT ["python", "/app/src/main.py"]
