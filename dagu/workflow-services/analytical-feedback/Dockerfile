FROM python:3.12-alpine
WORKDIR /app
COPY workflow_io.py ./src/workflow_io.py
COPY one-to-one-graph-matching/src/artifacts.py one-to-one-graph-matching/src/graph_index.py ./src/
COPY analytical-feedback/src/ ./src/
COPY analytical-feedback/schemas/ ./schemas/
ENTRYPOINT ["python", "/app/src/main.py"]
