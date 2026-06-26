# ANDS Forge OS — container image for the FastAPI edge (offline-deterministic by default).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FORGE_WORKSPACE=/data \
    PORT=8099

WORKDIR /app

COPY pyproject.toml requirements.txt README.md ./
COPY src ./src
COPY scripts ./scripts
COPY evals ./evals

RUN pip install --no-cache-dir . \
    && mkdir -p /data

EXPOSE 8099

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8099/health').status==200 else 1)"

CMD ["uvicorn", "forge_os.api:app", "--host", "0.0.0.0", "--port", "8099"]
