# Agent runtime image (Day 13). Multi-stage: a builder resolves deps into a venv, the
# runtime stage is a slim, non-root image with only the venv + source + datasets.
#
# IMPORTANT: build from the repo root (ai-secops-copilot) so `datasets/` is in context and
# the repo layout is preserved under /app — the runtime resolves datasets via repo-root
# relative paths (parents[3]/parents[4]), so keeping the layout means zero code changes:
#
#   docker build -f services/agent-runtime/Dockerfile -t secops-agent-runtime .
# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY services/agent-runtime/pyproject.toml services/agent-runtime/README.md ./
COPY services/agent-runtime/app ./app
RUN pip install --upgrade pip && pip install .

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8088
# Non-root runtime user; /data is a writable mount point for the SQLite backend.
RUN useradd --create-home --uid 10001 appuser && mkdir -p /data && chown appuser:appuser /data
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY services/agent-runtime ./services/agent-runtime
COPY datasets ./datasets
WORKDIR /app/services/agent-runtime
USER appuser
EXPOSE 8088
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,sys,urllib.request; p=os.environ.get('PORT','8088'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/health', timeout=3).status==200 else 1)"
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088"]
