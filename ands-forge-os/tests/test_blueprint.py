"""Blueprint schema: loading, validation, cycle + dangling-edge detection."""

from __future__ import annotations

import pytest

from forge_kernel.blueprint import BlueprintError, from_dict
from forge_os import load_program_blueprint


def test_program_blueprint_loads_and_validates():
    bp = load_program_blueprint()
    assert bp.name == "ands-forge-os"
    keys = [s.key for s in bp.ordered_stages()]
    assert keys[0] == "intake"
    assert "scaffold" in keys
    # stub stages present and flagged
    assert bp.stage("security").auto_pass is True


def test_dangling_edge_rejected():
    data = {
        "name": "x", "version": "1",
        "stages": [
            {"key": "s1", "artifacts": [
                {"key": "a", "role": "r", "depends_on": ["does_not_exist"]},
            ]},
        ],
    }
    with pytest.raises(BlueprintError):
        from_dict(data)


def test_cycle_rejected():
    data = {
        "name": "x", "version": "1",
        "stages": [
            {"key": "s1", "artifacts": [
                {"key": "a", "role": "r", "depends_on": ["b"]},
                {"key": "b", "role": "r", "depends_on": ["a"]},
            ]},
        ],
    }
    with pytest.raises(BlueprintError):
        from_dict(data)


def test_bad_gate_mode_rejected():
    data = {
        "name": "x", "version": "1",
        "stages": [{"key": "s1", "gate_mode": "nonsense", "artifacts": [
            {"key": "a", "role": "r"}]}],
    }
    with pytest.raises(BlueprintError):
        from_dict(data)
