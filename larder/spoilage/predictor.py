"""Predict which inventory items spoil first.

The LLM path is tried when a client is passed in. Any failure — missing key,
timeout, bad JSON — falls back to the shelf-life table. The kitchen plan
still runs with the network unplugged.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from pydantic import BaseModel, ValidationError

from larder.llm.client import LLMClient, LLMError
from larder.llm.prompts import spoilage_messages
from larder.models import InventoryItem, RiskLevel, SpoilageRisk
from larder.spoilage.shelf_life import baseline_days


class SpoilageReport(BaseModel):
    """JSON object the model is asked to return."""

    risks: list[SpoilageRisk]


def risk_band(days_remaining: int) -> RiskLevel:
    """Map days left onto the four risk labels."""
    if days_remaining <= 0:
        return "critical"
    if days_remaining <= 2:
        return "high"
    if days_remaining <= 5:
        return "medium"
    return "low"


def heuristic_risks(
    items: list[InventoryItem],
    today: date | None = None,
) -> list[SpoilageRisk]:
    """Estimate spoilage from expiry dates, then from the shelf-life table.

    An explicit ``expires_on`` wins. Otherwise the days left are the table
    value minus how long the item has already been in the kitchen.
    """
    today = today or date.today()
    risks: list[SpoilageRisk] = []
    for item in items:
        if not item.is_food:
            continue
        days, reason = _days_and_reason(item, today)
        risks.append(
            SpoilageRisk(
                item_id=item.id,
                item_name=item.name,
                risk=risk_band(days),
                days_remaining=days,
                reason=reason,
                source="heuristic",
            )
        )
    return _sorted(risks)


def predict_spoilage(
    items: list[InventoryItem],
    *,
    client: LLMClient | None = None,
    today: date | None = None,
) -> list[SpoilageRisk]:
    """Return one risk per item, soonest first.

    Pass ``client=None`` to force the heuristic. The Streamlit app passes
    ``LLMClient.from_env()``, which is ``None`` when no API key is set.
    """
    today = today or date.today()
    considered = [item for item in items if item.is_food]
    if not considered:
        return []
    fallback = heuristic_risks(considered, today=today)
    if client is None:
        return fallback
    try:
        system, user = spoilage_messages(considered, today)
        report = client.complete_json(system=system, user=user, schema=SpoilageReport)
        if not isinstance(report, SpoilageReport):
            report = SpoilageReport.model_validate(report)
    except (LLMError, ValidationError, ValueError, TypeError, KeyError):
        return fallback
    return _merge(report.risks, considered, today)


def _days_and_reason(item: InventoryItem, today: date) -> tuple[int, str]:
    if item.expires_on is not None:
        days = (item.expires_on - today).days
        when = item.expires_on.isoformat()
        if days < 0:
            reason = f"Expiry {when} was {abs(days)} day(s) ago."
        elif days == 0:
            reason = f"Expires today ({when})."
        else:
            reason = f"Expires on {when} ({days} day(s) left)."
        return days, reason

    shelf = baseline_days(item.name, item.category)
    elapsed = (today - item.acquired_on).days
    days = shelf - elapsed
    reason = (
        f"No expiry date. The shelf-life table gives {item.name} {shelf} day(s) "
        f"from {item.acquired_on.isoformat()}, so {days} day(s) remain."
    )
    return days, reason


def _merge(
    llm_risks: list[SpoilageRisk],
    items: list[InventoryItem],
    today: date,
) -> list[SpoilageRisk]:
    """Keep model rows for known items and fill anything it skipped."""
    heuristic = {risk.item_id: risk for risk in heuristic_risks(items, today=today)}
    merged: dict[str, SpoilageRisk] = {}
    for risk in llm_risks:
        if risk.item_id not in heuristic:
            continue
        merged[risk.item_id] = risk.model_copy(
            update={
                "source": "llm",
                "item_name": heuristic[risk.item_id].item_name,
            }
        )
    for item_id, risk in heuristic.items():
        merged.setdefault(item_id, risk)
    return _sorted(merged.values())


def _sorted(risks: Iterable[SpoilageRisk]) -> list[SpoilageRisk]:
    return sorted(risks, key=lambda risk: (risk.days_remaining, risk.item_name))
