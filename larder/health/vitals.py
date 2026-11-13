"""A recorded wearable reading: heart rate, oxygen, stress, and breathing.

There is no live wearable yet. The dashboard shows ``fixtures/vitals.sample.json``
so the body side of the conditions banner has numbers to stand next to the weather.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from larder import project_root


class Vitals(BaseModel):
    """One wearable snapshot. Scores are the device's own units."""

    captured_at: datetime
    heart_rate_bpm: int = Field(ge=20, le=220)
    spo2_percent: int = Field(ge=50, le=100)
    stress: int = Field(ge=0, le=100)
    respiration_per_min: int = Field(ge=4, le=60)


def stress_label(score: int) -> str:
    """Turn a 0–100 stress score into a short word."""
    if score < 35:
        return "Low"
    if score < 65:
        return "Moderate"
    return "High"


def load_vitals(path: Path | None = None) -> Vitals:
    """Read the sample wearable fixture."""
    fixture = path or (project_root() / "fixtures" / "vitals.sample.json")
    if not fixture.is_file():
        raise FileNotFoundError(f"Vitals fixture not found: {fixture}")
    return Vitals.model_validate(json.loads(fixture.read_text(encoding="utf-8")))
