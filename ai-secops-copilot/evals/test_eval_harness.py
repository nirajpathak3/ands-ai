"""Self-tests for the evaluation harness (metrics, retrieval eval, judge, gate).

Run from the repo root:  python -m pytest evals -q
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import judge as judge_mod  # noqa: E402
import metrics  # noqa: E402
import retrieval_eval  # noqa: E402
import run_eval  # noqa: E402


# --- metrics -----------------------------------------------------------------

def test_accuracy_and_binary_prf():
    assert metrics.accuracy([("a", "a"), ("a", "b")]) == 0.5
    prf = metrics.binary_prf([True, False, True], [True, False, False])
    assert prf["tp"] == 1 and prf["fp"] == 1 and prf["tn"] == 1


# --- retrieval evaluation ----------------------------------------------------

def test_retrieval_eval_hits_in_kb():
    dataset = run_eval.load_dataset(run_eval.DEFAULT_DATASET)
    result = retrieval_eval.evaluate_retrieval(dataset, k=3)
    assert result["available"] is True
    assert result["evaluated"] > 0
    # Exact CWE id boost -> the relevant doc should rank first for in-KB findings.
    assert result["hitRateAt1"] == 1.0
    assert result["hitRateAtK"] == 1.0
    assert 0.0 < result["coverage"] <= 1.0


def test_relevant_doc_id_mapping():
    assert retrieval_eval._relevant_doc_id("CWE-89") == "cwe-89"
    assert retrieval_eval._relevant_doc_id("cwe-1004") == "cwe-1004"


# --- LLM-as-judge ------------------------------------------------------------

def test_judge_rewards_consistent_reasoning():
    j = judge_mod.get_judge("deterministic")
    good = {"severity": "critical", "action": "create_ticket", "confidence": 0.95,
            "reason": "Untrusted user input reaches a SQL sink; real injection. Open a ticket."}
    assert j.score({}, good)["overall"] == 1.0


def test_judge_penalizes_inconsistent_action():
    j = judge_mod.get_judge("deterministic")
    bad = {"severity": "critical", "action": "suppress", "confidence": 0.95,
           "reason": "short"}
    res = j.score({}, bad)
    assert res["checks"]["action_consistent"] is False
    assert res["checks"]["reason_present"] is False
    assert res["overall"] < 1.0


def test_evaluate_judge_aggregates():
    dataset = run_eval.load_dataset(run_eval.DEFAULT_DATASET)
    predictor = run_eval.predictors.get_predictor("runtime")
    result = judge_mod.evaluate_judge(
        dataset["findings"], predictor, judge_mod.get_judge("deterministic")
    )
    assert result["count"] == len(dataset["findings"])
    assert 0.0 <= result["overall"] <= 1.0


# --- end-to-end gate ---------------------------------------------------------

def test_run_eval_all_gate_passes_for_runtime():
    rc = run_eval.main(
        ["--predictor", "runtime", "--all", "--gate", "--no-write", "--quiet"]
    )
    assert rc == 0


def test_run_eval_gate_fails_on_impossible_threshold():
    rc = run_eval.main(
        ["--predictor", "heuristic", "--gate", "--no-write", "--quiet",
         "--min-severity-accuracy", "1.01"]
    )
    assert rc == 1
