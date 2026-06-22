# Common developer tasks. (Windows users without `make`: run the underlying
# commands shown for each target, or use Git Bash / WSL.)

.PHONY: help eval eval-gate infra-up infra-down runtime-install runtime-test gateway-install gateway-test test

help:
	@echo "Targets:"
	@echo "  eval             Run the evaluation harness (heuristic baseline)"
	@echo "  eval-gate        Run evals with the regression gate (CI)"
	@echo "  infra-up         Start Postgres (pgvector) + Redis via docker compose"
	@echo "  infra-down       Stop local infrastructure"
	@echo "  runtime-install  Install agent-runtime deps (editable + dev extras)"
	@echo "  runtime-test     Run agent-runtime unit tests"
	@echo "  gateway-install  Install gateway deps"
	@echo "  gateway-test     Run gateway unit tests"
	@echo "  test             Run evals + both service test suites"

eval:
	python evals/run_eval.py

eval-gate:
	python evals/run_eval.py --gate

infra-up:
	docker compose up -d

infra-down:
	docker compose down

runtime-install:
	cd services/agent-runtime && pip install -e ".[dev]"

runtime-test:
	cd services/agent-runtime && pytest

gateway-install:
	cd services/gateway && npm install

gateway-test:
	cd services/gateway && npm test

test: eval-gate runtime-test gateway-test
