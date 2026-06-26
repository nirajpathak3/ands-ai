# ANDS Forge OS — developer + CI shortcuts. Mirrors what CI runs.
#   make install   # editable install with dev extras
#   make check     # lint + tests + eval gate (the full local gate, == CI)
#   make demo      # narrated offline end-to-end walkthrough (no server/keys)
#   make serve     # run the API + dashboard locally
#   make up        # build + start via docker compose

.PHONY: help install lint test eval gate check demo demo-live serve up down clean

help:
	@echo "install  - pip install -e .[graph,llm,dev]"
	@echo "lint     - ruff check"
	@echo "test     - pytest"
	@echo "gate     - eval regression gate"
	@echo "check    - lint + test + gate (full local gate, == CI)"
	@echo "demo     - offline end-to-end walkthrough"
	@echo "serve    - uvicorn API + dashboard on :8099"
	@echo "up/down  - docker compose up --build / down"

install:
	python -m pip install -e ".[graph,llm,dev]"

lint:
	ruff check src tests evals scripts

test:
	pytest -q

gate:
	python evals/run_eval.py --gate

check: lint test gate

demo:
	python scripts/demo_walkthrough.py

demo-live:
	python scripts/demo_live_fake.py

serve:
	uvicorn forge_os.api:app --reload --port 8099

up:
	docker compose up -d --build

down:
	docker compose down

clean:
	rm -rf var runs out .pytest_cache .ruff_cache
