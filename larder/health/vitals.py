"""A recorded wearable reading: heart rate, oxygen, stress, and breathing.

There is no live wearable yet. The dashboard shows ``fixtures/vitals.sample.json``
so the body side of the conditions banner has numbers to stand next to the weather.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from larder import project_root
from larder.grow.balance import CALORIES, PROTEIN, find_gaps
from larder.models import InventoryItem, SpoilageRisk

# A wearer working hard (hauling water, digging) burns through stores faster.
# These are activity cues for the food plan, not a medical judgement.
EXERTION_HEART_RATE = 100
EXERTION_RESPIRATION = 20


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


def try_load_vitals(path: Path | None = None) -> Vitals | None:
    """The wearable reading, or ``None`` if there is no usable one."""
    try:
        return load_vitals(path)
    except (FileNotFoundError, ValidationError, ValueError):
        return None


def is_exerting(vitals: Vitals | None) -> bool:
    if vitals is None:
        return False
    return (
        vitals.heart_rate_bpm >= EXERTION_HEART_RATE
        or vitals.respiration_per_min >= EXERTION_RESPIRATION
    )


def body_needs(vitals: Vitals | None) -> list[str]:
    """Food groups the body asks for right now, from the wearable."""
    return [CALORIES, PROTEIN] if is_exerting(vitals) else []


def body_note(vitals: Vitals | None) -> str:
    """One plain sentence on what the vitals mean for the food plan."""
    if vitals is None:
        return "No wearable reading, so the plan follows the pantry alone."
    if is_exerting(vitals):
        return (
            f"Heart rate {vitals.heart_rate_bpm} bpm and breathing {vitals.respiration_per_min}/min: "
            "you're working hard, so meals with calorie staples and protein go first."
        )
    return (
        f"Heart rate {vitals.heart_rate_bpm} bpm at rest: no extra demand on food today, "
        "so the plan follows what spoils first and what the shelf is short on."
    )


def survival_needs(
    items: list[InventoryItem],
    risks: list[SpoilageRisk] | None,
    vitals: Vitals | None,
    today: date | None = None,
) -> list[str]:
    """What to cook toward: the shelf's thin food groups plus the body's demand."""
    needs = find_gaps([i for i in items if i.is_food], risks=risks, today=today)
    for group in body_needs(vitals):
        if group not in needs:
            needs.append(group)
    return needs
