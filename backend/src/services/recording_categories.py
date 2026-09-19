"""Loader for the shared recording-category catalog.

Single source of truth: `shared/recording-categories.json` at the repo root,
consumed by BOTH the backend (enforcement) and the frontend (picker + validation)
so the "which category requires a project" rule cannot drift between them.

The file holds data only (value / kind / requiresProject); UI labels stay in the
frontend because the backend has no use for presentation text.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RecordingCategory:
    value: str
    kind: str  # "cost" | "expense"
    requires_project: bool


def _default_catalog_path() -> Path:
    """Resolve shared/recording-categories.json from the repo root.

    File-relative (not CWD-relative) so it works whether the process runs from
    the repo root, from `backend/`, or from a test runner with any working dir.
    """
    return Path(__file__).resolve().parents[3] / "shared" / "recording-categories.json"


def load_recording_categories(path: Optional[Path] = None) -> list[RecordingCategory]:
    """Load the canonical catalog. Raises FileNotFoundError if it is missing.

    Failing loud is deliberate: a silently empty catalog would quietly disable
    the project-required rule on both sides.
    """
    target = path or _default_catalog_path()
    raw = json.loads(target.read_text(encoding="utf-8"))
    return [
        RecordingCategory(
            value=entry["value"],
            kind=entry["kind"],
            requires_project=bool(entry["requiresProject"]),
        )
        for entry in raw
    ]


def _project_required_cost_categories() -> set[str]:
    return {
        entry.value
        for entry in load_recording_categories()
        if entry.kind == "cost" and entry.requires_project
    }


# Derived once at import: the cost categories that must carry a project.
PROJECT_REQUIRED_COST_CATEGORIES: set[str] = _project_required_cost_categories()
