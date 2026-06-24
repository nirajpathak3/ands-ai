"""Day 18: in-process scheduler + background jobs (SLA sweep, reconcile, DLQ retry)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import _retry_dead_letters, app
from app.scheduler import Scheduler
from app.ticketing import (
    ApprovalStore,
    DeadLetterQueue,
    EscalationQueue,
    MockTicketProvider,
)

client = TestClient(app)


# --- Scheduler unit ---------------------------------------------------------

def test_run_job_records_success():
    sched = Scheduler()

    async def job():
        return {"did": 1}

    sched.register("j", 60, job)
    state = asyncio.run(sched.run_job("j"))
    assert state.runs == 1
    assert state.last_status == "ok"
    assert state.last_result == {"did": 1}
    assert state.last_error is None


def test_run_job_captures_error():
    sched = Scheduler()

    async def job():
        raise RuntimeError("boom")

    sched.register("j", 60, job)
    state = asyncio.run(sched.run_job("j"))
    assert state.last_status == "error"
    assert state.errors == 1
    assert "boom" in (state.last_error or "")


def test_run_unknown_job_raises():
    sched = Scheduler()
    with pytest.raises(KeyError):
        asyncio.run(sched.run_job("nope"))


def test_register_is_idempotent():
    sched = Scheduler()

    async def job():
        return {}

    sched.register("j", 1, job)
    sched.register("j", 999, job)  # ignored
    assert sched.names == ["j"]
    assert sched.status()[0]["interval_s"] == 1


def test_start_runs_periodically_then_stops():
    async def scenario():
        sched = Scheduler()
        counter = {"n": 0}

        async def job():
            counter["n"] += 1
            return {"n": counter["n"]}

        sched.register("tick", 0.01, job)
        sched.start()
        assert sched.is_running
        await asyncio.sleep(0.06)
        await sched.stop()
        return counter["n"], sched.is_running

    n, running = asyncio.run(scenario())
    assert n >= 1
    assert running is False


# --- dead-letter retry helper ----------------------------------------------

def test_retry_dead_letters_recovers():
    dlq = DeadLetterQueue()
    dlq.add(
        {
            "findingHash": "h1", "findingId": "F-1", "disposition": "auto_execute",
            "analysis": {"severity": "high", "recommendedAction": "create_ticket"},
        },
        error="provider down",
    )
    ctx = SimpleNamespace(
        dead_letter=dlq, provider=MockTicketProvider(),
        approvals=ApprovalStore(), escalations=EscalationQueue(),
    )
    result = _retry_dead_letters(ctx)
    assert result == {"retried": 1, "recovered": 1}
    assert dlq.list_all() == []  # recovered items are not re-queued


def test_retry_dead_letters_empty():
    ctx = SimpleNamespace(
        dead_letter=DeadLetterQueue(), provider=MockTicketProvider(),
        approvals=ApprovalStore(), escalations=EscalationQueue(),
    )
    assert _retry_dead_letters(ctx) == {"retried": 0, "recovered": 0}


# --- API --------------------------------------------------------------------

def test_jobs_listed_and_idle():
    body = client.get("/jobs").json()
    assert body["schedulerEnabled"] is False
    assert body["running"] is False
    names = {j["name"] for j in body["jobs"]}
    assert {"sla_sweep", "provider_reconcile", "deadletter_retry"} <= names


def test_run_sla_sweep_on_demand():
    client.post("/demo/reset", headers={"X-Tenant-Id": "jobs-api"})
    client.post("/demo/seed", headers={"X-Tenant-Id": "jobs-api"})
    state = client.post("/jobs/run/sla_sweep").json()
    assert state["last_status"] == "ok"
    assert state["runs"] >= 1
    assert "tenants" in state["last_result"]
    assert "breaches" in state["last_result"]


def test_run_reconcile_and_deadletter_jobs():
    recon = client.post("/jobs/run/provider_reconcile").json()
    assert recon["last_status"] == "ok"
    assert "reconciled" in recon["last_result"]

    dlq = client.post("/jobs/run/deadletter_retry").json()
    assert dlq["last_status"] == "ok"
    assert "retried" in dlq["last_result"]


def test_run_unknown_job_404():
    assert client.post("/jobs/run/nope").status_code == 404
