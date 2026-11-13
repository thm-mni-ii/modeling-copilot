FROM python:3.12-alpine
WORKDIR /app
COPY workflow_io.py ./src/workflow_io.py
COPY feedback-generation/src/ ./src/
COPY analytical-feedback/src/analysis_contract.py ./src/analysis_contract.py
ENTRYPOINT ["python", "/app/src/main.py"]
