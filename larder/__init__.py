"""Fallow: a kitchen inventory, spoilage, and garden planner."""

from pathlib import Path


def project_root() -> Path:
    """Return the repository root (the directory that contains ``larder``)."""
    return Path(__file__).resolve().parents[1]
