"""Turn a sensor snapshot into a short planting list.

Rules, not a model: frost and cold months get cold-hardy crops, warm months
get crops that actually need heat, and dry soil drops the thirsty greens.
The snapshot's own timestamp picks the season, so a saved fixture stays the
same demo on any day you open it.
"""

from __future__ import annotations

from datetime import date, datetime

from larder.grow.balance import explain_balance, find_gaps
from larder.lifecycle import compost_ready_on
from larder.models import GrowCrop, GrowPlan, InventoryItem, SpoilageRisk
from larder.sensors.base import SensorSnapshot

_COLD_MONTHS = {11, 12, 1, 2, 3}
_WARM_MONTHS = {5, 6, 7, 8, 9}


def advise(snapshot: SensorSnapshot, today: date | None = None) -> list[GrowCrop]:
    """Return the crops that fit this weather and soil."""
    when = today or _snapshot_day(snapshot.captured_at)
    cold = snapshot.frost_risk or snapshot.temp_c <= 8 or when.month in _COLD_MONTHS
    warm = (
        not snapshot.frost_risk
        and snapshot.temp_c >= 18
        and when.month in _WARM_MONTHS
    )
    if cold and not warm:
        crops = [
            GrowCrop(
                crop="kale",
                action="plant now",
                reason="Kale keeps producing after a frost and replaces fresh food.",
                fills="fresh food",
            ),
            GrowCrop(
                crop="spinach",
                action="plant now",
                reason="A short cold-season green for the weeks the fridge runs low.",
                fills="fresh food",
            ),
            GrowCrop(
                crop="garlic",
                action="plant now",
                reason="Garlic overwinters and stores, which steadies the calorie shelf.",
                fills="calorie staples",
            ),
        ]
    elif warm:
        crops = [
            GrowCrop(
                crop="bush beans",
                action="plant now",
                reason="Beans add protein you can dry and keep.",
                fills="protein",
            ),
            GrowCrop(
                crop="potatoes",
                action="plant now",
                reason="Potatoes are the calorie crop that stores in a cool cupboard.",
                fills="calorie staples",
            ),
            GrowCrop(
                crop="chard",
                action="plant now",
                reason="Chard is the fresh food that keeps picking through summer.",
                fills="fresh food",
            ),
        ]
    else:
        crops = [
            GrowCrop(
                crop="kale",
                action="plant now",
                reason="Shoulder season still suits a frost-tolerant green.",
                fills="fresh food",
            ),
            GrowCrop(
                crop="peas",
                action="plant now",
                reason="Peas like cool soil and add protein before the heat arrives.",
                fills="protein",
            ),
            GrowCrop(
                crop="radishes",
                action="plant now",
                reason="Radishes are ready quickly if fresh food is the thin spot.",
                fills="fresh food",
            ),
        ]

    if _soil_is_dry(snapshot):
        crops = [crop for crop in crops if crop.crop != "spinach"]
        crops.append(
            GrowCrop(
                crop="thyme",
                action="plant now",
                reason="Dry soil favors an herb over thirsty greens. Water deeply, less often.",
                fills="fresh food",
            )
        )
    return crops


def build_grow_plan(
    snapshot: SensorSnapshot,
    items: list[InventoryItem],
    today: date | None = None,
    risks: list[SpoilageRisk] | None = None,
) -> GrowPlan:
    """Advise what to plant and say how that lines up with the pantry.

    Pass the spoilage ``risks`` you already computed so the gap check uses
    the same days-left numbers as the dashboard. Omit them and the gap check
    uses the shelf-life table.
    """
    when = today or _snapshot_day(snapshot.captured_at)
    crops = advise(snapshot, today=when)
    gaps = find_gaps(items, risks=risks, today=when)
    return GrowPlan(
        location=snapshot.location,
        crops=crops,
        gaps=gaps,
        balance_notes=explain_balance(gaps, crops),
        soil_notes=soil_notes(items, when),
    )


def soil_notes(items: list[InventoryItem], today: date) -> str:
    """Say what the compost loop has ready to feed the next planting."""
    finished = [i for i in items if i.state == "soil_amendment" and i.quantity > 0]
    piles = [i for i in items if i.state == "compost" and i.quantity > 0]
    sentences: list[str] = []
    if finished:
        names = ", ".join(f"{i.quantity:g} {i.unit} {i.name}" for i in finished)
        sentences.append(f"Finished compost on hand ({names}): dig it in before planting.")
    for pile in piles:
        ready = compost_ready_on(pile)
        if ready is None:
            continue
        if ready <= today:
            sentences.append(f"The {pile.name} pile is ready to screen into soil amendment.")
        else:
            sentences.append(f"The {pile.name} pile should be finished around {ready.isoformat()}.")
    return " ".join(sentences)


def _snapshot_day(captured_at: datetime) -> date:
    return captured_at.date()


def _soil_is_dry(snapshot: SensorSnapshot) -> bool:
    if snapshot.soil_moisture is not None and snapshot.soil_moisture < 0.3:
        return True
    # A wet surface after a shower can hide a dry root zone.
    if snapshot.soil_moisture_root is not None and snapshot.soil_moisture_root < 0.3:
        return True
    text = snapshot.soil_condition.lower()
    return "dry" in text or "dust" in text
