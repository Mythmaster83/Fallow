"""Build a short cooking plan from the inventory alone.

Nothing on the plan is a shopping item. Every meal points at ids that exist
in the inventory you passed in. Shelf-stable food is used only as a base
under something that is about to spoil.
"""

from __future__ import annotations

from datetime import date

from larder.models import InventoryItem, MealPlan, PlannedMeal, SpoilageRisk
from larder.spoilage.predictor import heuristic_risks

_STAPLE_CATEGORIES = {"grain", "pantry", "bread"}

_MEAL_NAMES = {
    "leafy_greens": "Wilted greens on a staple base",
    "produce": "Roast the vegetables that will go first",
    "berries": "Bowl the soft fruit before it slumps",
    "meat": "Skillet for the meat that is closest to spoiling",
    "fish": "Pan the fish tonight",
    "dairy": "Finish the open dairy over grains",
    "eggs": "Eggs with whatever is softest",
    "bread": "Use the bread before it stales",
    "leftovers": "Second-day skillet",
    "herb": "Fold the herbs into a staple bowl",
}


def plan_meals(
    items: list[InventoryItem],
    risks: list[SpoilageRisk] | None = None,
    horizon_days: int = 3,
    today: date | None = None,
) -> MealPlan:
    """Plan up to ``horizon_days`` meals from food already on hand.

    Low-risk items do not get their own meal. They can ride along as the
    staple base under something urgent. A risk whose id is not in the
    inventory is ignored, so a model cannot invent a food you do not have.
    """
    if horizon_days < 1:
        raise ValueError("horizon_days must be at least 1")

    active = [item for item in items if item.quantity > 0]
    by_id = {item.id: item for item in active}
    if not active:
        return MealPlan(
            horizon_days=horizon_days,
            meals=[],
            priority_item_ids=[],
            summary="The inventory is empty, so there is nothing to cook.",
        )

    usable = _risks_for(active, risks, today)
    urgent = [risk for risk in usable if risk.risk != "low"]
    priority_ids = [risk.item_id for risk in urgent]
    if not urgent:
        return MealPlan(
            horizon_days=horizon_days,
            meals=[],
            priority_item_ids=[],
            summary="Nothing in the inventory is close to spoiling.",
        )

    risks_by_id = {risk.item_id: risk for risk in usable}
    staple = _calmest_staple(active, risks_by_id)
    meals: list[PlannedMeal] = []
    for index, risk in enumerate(urgent[:horizon_days], start=1):
        item = by_id[risk.item_id]
        item_ids = [item.id]
        uses = [item.name]
        if staple is not None and staple.id != item.id:
            item_ids.append(staple.id)
            uses.append(staple.name)
        meals.append(
            PlannedMeal(
                day=index,
                name=_MEAL_NAMES.get(item.category, f"Cook the {item.name} first"),
                item_ids=item_ids,
                uses=uses,
                why=_why(item, risk),
            )
        )

    lead_names = [by_id[item_id].name for item_id in priority_ids[:3]]
    summary = (
        f"Plan for the next {horizon_days} day(s): cook {', '.join(lead_names)} first "
        "so they do not go to waste."
    )
    return MealPlan(
        horizon_days=horizon_days,
        meals=meals,
        priority_item_ids=priority_ids,
        summary=summary,
    )


def _risks_for(
    items: list[InventoryItem],
    risks: list[SpoilageRisk] | None,
    today: date | None,
) -> list[SpoilageRisk]:
    if risks is None:
        return heuristic_risks(items, today=today)
    known = {item.id for item in items}
    kept = [risk for risk in risks if risk.item_id in known]
    covered = {risk.item_id for risk in kept}
    missing = [item for item in items if item.id not in covered]
    if missing:
        kept.extend(heuristic_risks(missing, today=today))
    ordered = sorted(kept, key=lambda risk: (risk.days_remaining, risk.item_name))
    seen: set[str] = set()
    unique: list[SpoilageRisk] = []
    for risk in ordered:
        if risk.item_id in seen:
            continue
        seen.add(risk.item_id)
        unique.append(risk)
    return unique


def _calmest_staple(
    items: list[InventoryItem],
    risks_by_id: dict[str, SpoilageRisk],
) -> InventoryItem | None:
    staples = [item for item in items if item.category in _STAPLE_CATEGORIES]
    if not staples:
        return None
    return max(staples, key=lambda item: risks_by_id[item.id].days_remaining)


def _why(item: InventoryItem, risk: SpoilageRisk) -> str:
    if risk.days_remaining < 0:
        timing = f"{item.name} is already overdue"
    elif risk.days_remaining == 0:
        timing = f"{item.name} expires today"
    else:
        timing = f"{item.name} has {risk.days_remaining} day(s) left"
    return f"{timing} ({risk.risk} risk). Cook it before opening food that can wait."
