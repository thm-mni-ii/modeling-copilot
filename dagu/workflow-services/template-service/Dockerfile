FROM python:3.12-alpine

WORKDIR /app
COPY workflow_io.py ./src/workflow_io.py
COPY template-service/src/ ./src/

ENTRYPOINT ["python", "/app/src/main.py"]
