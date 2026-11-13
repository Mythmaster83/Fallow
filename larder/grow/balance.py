"""Compare the pantry with what a garden can replace.

A group counts as covered only when some food in that group will still be
good after a few days. Chicken that must be cooked tonight does not count
as stored protein. Dry or canned beans do: the name is the protein, even
though the category is pantry.
"""

from __future__ import annotations

from datetime import date

from larder.models import GrowCrop, InventoryItem, SpoilageRisk
from larder.spoilage.predictor import heuristic_risks

FRESH = "fresh food"
CALORIES = "calorie staples"
PROTEIN = "protein"

_FRESH_CATEGORIES = {"leafy_greens", "produce", "berries", "herb"}
_CALORIE_CATEGORIES = {"grain", "pantry", "bread"}
_PROTEIN_CATEGORIES = {"meat", "fish", "eggs", "dairy"}
_LEGUMES = {"beans", "bean", "lentils", "lentil", "tofu", "chickpeas", "chickpea"}

# Food that expires inside this window is not a reserve.
RESERVE_DAYS = 3


def find_gaps(
    items: list[InventoryItem],
    risks: list[SpoilageRisk] | None = None,
    today: date | None = None,
) -> list[str]:
    """Return the reserve groups the pantry cannot cover past the short window."""
    active = [item for item in items if item.is_food]
    if risks is None:
        risks = heuristic_risks(active, today=today)
    by_id = {risk.item_id: risk for risk in risks}
    gaps: list[str] = []
    for label in (FRESH, CALORIES, PROTEIN):
        if not _has_reserve(active, by_id, label):
            gaps.append(label)
    return gaps


def explain_balance(gaps: list[str], crops: list[GrowCrop]) -> str:
    """Say which gaps the planting list covers and which stay open."""
    if not gaps:
        return (
            "The pantry already holds fresh food, calorie staples, and protein "
            "past the next few days. Planting now is for the following season, "
            "not an emergency."
        )
    fills = {crop.fills for crop in crops if crop.action == "plant now"}
    covered = [gap for gap in gaps if gap in fills]
    still_open = [gap for gap in gaps if gap not in fills]
    sentences: list[str] = []
    if covered:
        sentences.append(f"Planting covers the gap in {_join(covered)}.")
    if still_open:
        sentences.append(
            f"Still thin on {_join(still_open)}; this weather will not grow that quickly."
        )
    return " ".join(sentences)


def _has_reserve(
    items: list[InventoryItem],
    by_id: dict[str, SpoilageRisk],
    label: str,
) -> bool:
    for item in items:
        risk = by_id.get(item.id)
        if risk is None or risk.days_remaining <= RESERVE_DAYS:
            continue
        if label in _buckets(item):
            return True
    return False


def buckets_for(item: InventoryItem) -> set[str]:
    """The food groups one item counts toward."""
    return _buckets(item)


def _buckets(item: InventoryItem) -> set[str]:
    buckets: set[str] = set()
    if item.category in _FRESH_CATEGORIES:
        buckets.add(FRESH)
    if item.category in _CALORIE_CATEGORIES:
        buckets.add(CALORIES)
    if item.category in _PROTEIN_CATEGORIES:
        buckets.add(PROTEIN)
    name = item.name.strip().lower()
    if name in _LEGUMES or any(name.endswith(f" {legume}") for legume in _LEGUMES):
        buckets.add(PROTEIN)
        buckets.add(CALORIES)
    return buckets


def _join(labels: list[str]) -> str:
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"
