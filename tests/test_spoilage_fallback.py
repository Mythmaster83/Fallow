"""The spoilage predictor must keep working when the model call fails."""

import json
from datetime import date, timedelta

import pytest

from larder.llm.client import LLMClient, LLMError
from larder.models import InventoryItem, SpoilageRisk
from larder.spoilage.predictor import SpoilageReport, heuristic_risks, predict_spoilage

TODAY = date(2026, 11, 13)


class ScriptedClient:
    """Stand-in for LLMClient. No network."""

    def __init__(self, result: SpoilageReport | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    def complete_json(self, *, system: str, user: str, schema: type) -> SpoilageReport:
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _item(
    item_id: str,
    name: str,
    category: str,
    *,
    acquired_on: date | None = None,
    expires_on: date | None = None,
) -> InventoryItem:
    return InventoryItem(
        id=item_id,
        name=name,
        category=category,
        quantity=1,
        unit="count",
        acquired_on=acquired_on or TODAY,
        expires_on=expires_on,
        location="fridge",
    )


def test_no_client_uses_the_heuristic() -> None:
    items = [_item("spinach", "spinach", "leafy_greens", expires_on=TODAY + timedelta(days=1))]
    risks = predict_spoilage(items, client=None, today=TODAY)
    assert risks == heuristic_risks(items, today=TODAY)
    assert risks[0].source == "heuristic"


def test_failing_model_matches_the_table() -> None:
    items = [
        _item("spinach", "spinach", "leafy_greens", expires_on=TODAY + timedelta(days=1)),
        _item("rice", "rice", "grain", acquired_on=TODAY - timedelta(days=10)),
    ]
    client = ScriptedClient(error=LLMError("timeout"))
    assert predict_spoilage(items, client=client, today=TODAY) == heuristic_risks(items, today=TODAY)


def test_expiry_date_sets_days_remaining() -> None:
    items = [_item("chicken", "chicken", "meat", expires_on=TODAY + timedelta(days=1))]
    risk = heuristic_risks(items, today=TODAY)[0]
    assert risk.days_remaining == 1
    assert risk.risk == "high"
    assert "2026-11-14" in risk.reason


def test_overdue_expiry_is_critical() -> None:
    items = [_item("milk", "milk", "dairy", expires_on=TODAY - timedelta(days=2))]
    risk = heuristic_risks(items, today=TODAY)[0]
    assert risk.days_remaining == -2
    assert risk.risk == "critical"


def test_shelf_life_table_used_when_there_is_no_expiry() -> None:
    # Spinach lasts 4 days in the table. One day already in the kitchen leaves 3.
    items = [_item("spinach", "spinach", "leafy_greens", acquired_on=TODAY - timedelta(days=1))]
    risk = heuristic_risks(items, today=TODAY)[0]
    assert risk.days_remaining == 3
    assert risk.risk == "medium"
    assert "shelf-life table" in risk.reason


def test_soonest_item_is_first() -> None:
    items = [
        _item("rice", "rice", "grain", acquired_on=TODAY),
        _item("yogurt", "yogurt", "dairy", expires_on=TODAY),
    ]
    risks = heuristic_risks(items, today=TODAY)
    assert [risk.item_id for risk in risks] == ["yogurt", "rice"]


def test_unknown_model_item_is_dropped() -> None:
    items = [_item("rice", "rice", "grain")]
    ghost = SpoilageRisk(
        item_id="quinoa",
        item_name="quinoa",
        risk="critical",
        days_remaining=0,
        reason="not in the kitchen",
        source="llm",
    )
    client = ScriptedClient(result=SpoilageReport(risks=[ghost]))
    risks = predict_spoilage(items, client=client, today=TODAY)
    assert [risk.item_id for risk in risks] == ["rice"]
    assert risks[0].source == "heuristic"


def test_partial_model_report_fills_the_rest_from_the_table() -> None:
    items = [
        _item("spinach", "spinach", "leafy_greens", expires_on=TODAY + timedelta(days=1)),
        _item("rice", "rice", "grain"),
    ]
    spinach = SpoilageRisk(
        item_id="spinach",
        item_name="renamed by the model",
        risk="low",
        days_remaining=20,
        reason="model estimate",
        source="heuristic",
    )
    client = ScriptedClient(result=SpoilageReport(risks=[spinach]))
    risks = {risk.item_id: risk for risk in predict_spoilage(items, client=client, today=TODAY)}
    assert risks["spinach"].source == "llm"
    assert risks["spinach"].item_name == "spinach"
    assert risks["spinach"].days_remaining == 20
    assert risks["rice"].source == "heuristic"


def test_client_retries_invalid_json_then_validates() -> None:
    calls = {"n": 0}

    def transport(payload: dict) -> dict:
        calls["n"] += 1
        if calls["n"] == 1:
            return {"choices": [{"message": {"content": "not json"}}]}
        body = json.dumps({"risks": []})
        return {"choices": [{"message": {"content": body}}]}

    client = LLMClient(api_key="test-key", transport=transport, sleep=lambda _seconds: None, retries=2)
    report = client.complete_json(system="system", user="user", schema=SpoilageReport)
    assert report.risks == []
    assert calls["n"] == 2


def test_client_does_not_retry_unauthorized() -> None:
    calls = {"n": 0}

    def transport(payload: dict) -> dict:
        calls["n"] += 1
        raise LLMError("LLM HTTP 401: bad key")

    client = LLMClient(api_key="test-key", transport=transport, sleep=lambda _seconds: None, retries=2)
    with pytest.raises(LLMError, match="401"):
        client.complete_json(system="system", user="user", schema=SpoilageReport)
    assert calls["n"] == 1
