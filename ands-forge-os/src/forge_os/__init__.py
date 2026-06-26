"""ANDS Forge OS — the product-development PROGRAM running on the Forge kernel.

This package is *data + a thin roster*: it loads the lifecycle blueprint and skill packs
(both YAML), binds the agent roster, and hands them to the generic kernel. None of the
kernel changes to run this program — point it at a different blueprint + packs to build a
different kind of project.
"""

from __future__ import annotations

from .factory import PROGRAM_DIR, SKILLPACKS_DIR, build_forge, load_program_blueprint

__all__ = ["build_forge", "load_program_blueprint", "PROGRAM_DIR", "SKILLPACKS_DIR"]
