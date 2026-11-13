"""Body readings from a watch or pulse oximeter, plus air and radiation labels.

Fallow does not measure the body itself. A phone health platform (Apple
Health, Health Connect) or a Bluetooth oximeter would supply these numbers;
until one is connected, ``fixtures/body.sample.json`` stands in, the same way
the mock sensor stands in for the garden station.

The labels describe where a reading sits against common reference ranges.
They are wellness information, not a diagnosis.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from larder import project_root

Tone = Literal["good", "watch", "alert"]


class BodySnapshot(BaseModel):
    captured_at: datetime
    source: str = Field(min_length=1)
    spo2_pct: float | None = Field(default=None, ge=0, le=100)
    heart_rate_bpm: float | None = Field(default=None, ge=0)


def read_body_sample(path: Path | None = None) -> BodySnapshot:
    path = path or (project_root() / "fixtures" / "body.sample.json")
    return BodySnapshot.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def spo2_label(pct: float) -> tuple[str, Tone]:
    if pct >= 95:
        return "Typical range", "good"
    if pct >= 90:
        return "Below typical", "watch"
    return "Low, get checked", "alert"


def heart_rate_label(bpm: float) -> tuple[str, Tone]:
    if 60 <= bpm <= 100:
        return "Resting range", "good"
    return "Outside resting range", "watch"


def co2_label(ppm: float) -> tuple[str, Tone]:
    if ppm < 1000:
        return "Fresh air", "good"
    if ppm < 2000:
        return "Stuffy, ventilate", "watch"
    return "Ventilate now", "alert"


def radiation_label(usv_h: float) -> tuple[str, Tone]:
    if usv_h < 0.3:
        return "Normal background", "good"
    if usv_h < 1.0:
        return "Above background", "watch"
    return "High, take shelter", "alert"
