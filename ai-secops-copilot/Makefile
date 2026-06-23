# Developer + ops shortcuts (Day 13). Mirrors what CI runs.
#   make install   # install the agent-runtime (dev extra)
#   make check     # lint + tests + eval gate (the full local gate)
#   make up        # build + start the whole stack via docker compose

RUNTIME := services/agent-runtime

.PHONY: help install lint test eval-tests gate check \
        docker-runtime docker-gateway docker up down clean

help:
	@echo "install        - pip install -e agent-runtime[dev]"
	@echo "lint           - ruff check"
	@echo "test           - agent-runtime pytest"
	@echo "eval-tests     - evaluation harness self-tests"
	@echo "gate           - evaluation regression gate (runtime + RAG + judge + governance)"
	@echo "check          - lint + test + eval-tests + gate (full local gate, == CI)"
	@echo "docker         - build both container images"
	@echo "up / down      - docker compose up --build / down"

install:
	cd $(RUNTIME) && python -m pip install -e ".[dev]"

lint:
	cd $(RUNTIME) && ruff check .

test:
	cd $(RUNTIME) && pytest -q

eval-tests:
	python -m pytest evals -q

gate:
	python evals/run_eval.py --predictor runtime --all --gate --no-write

check: lint test eval-tests gate

docker-runtime:
	docker build -f $(RUNTIME)/Dockerfile -t secops-agent-runtime .

docker-gateway:
	docker build -t secops-gateway services/gateway

docker: docker-runtime docker-gateway

up:
	docker compose up -d --build

down:
	docker compose down
