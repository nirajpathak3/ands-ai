"""Assemble a configured ``Forge`` for the ANDS Forge OS product-development program."""

from __future__ import annotations

from pathlib import Path

from forge_kernel.blueprint import Blueprint, load_blueprint
from forge_kernel.config import Settings, get_settings
from forge_kernel.runner import Forge, RunStore
from forge_kernel.skillpack import SkillPackRegistry, load_registry

from .agents import build_registry
from .judge import make_gateway_judge

_PKG_DIR = Path(__file__).resolve().parent
PROGRAM_DIR = _PKG_DIR / "program"
SKILLPACKS_DIR = _PKG_DIR / "skillpacks"
BLUEPRINT_PATH = PROGRAM_DIR / "lifecycle.blueprint.yaml"


def load_program_blueprint() -> Blueprint:
    return load_blueprint(BLUEPRINT_PATH)


def load_program_skillpacks() -> SkillPackRegistry:
    return load_registry(SKILLPACKS_DIR)


def build_forge(settings: Settings | None = None, *, store: RunStore | None = None) -> Forge:
    """Build the Forge engine wired to the product-development blueprint + skill packs."""
    settings = settings or get_settings()
    return Forge(
        blueprint=load_program_blueprint(),
        agents=build_registry(),
        skillpacks=load_program_skillpacks(),
        settings=settings,
        store=store,
        judge_factory=make_gateway_judge,
    )
