"""Nutrition balance: which food groups the pantry holds in reserve.

This uses the same groups and the same reserve rule as ``larder.grow.balance``
(food that spoils within three days is not a reserve), so the Health page and
the garden plan never disagree about a gap.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

from larder.grow.balance import CALORIES, FRESH, PROTEIN, RESERVE_DAYS, buckets_for
from larder.models import InventoryItem, SpoilageRisk
from larder.spoilage.predictor import heuristic_risks

GroupStatus = Literal["covered", "short", "missing"]
GROUPS = (FRESH, CALORIES, PROTEIN)


class GroupReport(BaseModel):
    """One food group: what holds past the short window, and what does not."""

    group: str
    status: GroupStatus
    reserve: list[str]
    short: list[str]
    longest_days: int | None


class NutritionReport(BaseModel):
    groups: list[GroupReport]
    covered: int
    gaps: list[str]


def nutrition_report(
    items: list[InventoryItem],
    risks: list[SpoilageRisk] | None = None,
    today: date | None = None,
) -> NutritionReport:
    """Sort every active item into its groups and grade each group.

    ``covered``: at least one item lasts past the reserve window.
    ``short``: the group has food, but all of it spoils within the window.
    ``missing``: nothing in the pantry belongs to the group.
    """
    active = [item for item in items if item.quantity > 0]
    if risks is None:
        risks = heuristic_risks(active, today=today)
    by_id = {risk.item_id: risk for risk in risks}

    reports: list[GroupReport] = []
    for group in GROUPS:
        reserve: list[tuple[int, str]] = []
        short: list[tuple[int, str]] = []
        for item in active:
            if group not in buckets_for(item):
                continue
            risk = by_id.get(item.id)
            days = risk.days_remaining if risk else 0
            (reserve if days > RESERVE_DAYS else short).append((days, item.name))
        if reserve:
            status: GroupStatus = "covered"
        elif short:
            status = "short"
        else:
            status = "missing"
        every = reserve + short
        reports.append(
            GroupReport(
                group=group,
                status=status,
                reserve=[name for _, name in sorted(reserve, reverse=True)],
                short=[name for _, name in sorted(short)],
                longest_days=max(days for days, _ in every) if every else None,
            )
        )
    gaps = [r.group for r in reports if r.status != "covered"]
    return NutritionReport(groups=reports, covered=len(GROUPS) - len(gaps), gaps=gaps)
