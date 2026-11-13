"""Wearable vitals feed the food plan: working hard puts staples and protein first."""

from datetime import date, datetime, timedelta, timezone

from larder.health.vitals import Vitals, body_needs, body_note, survival_needs, try_load_vitals
from larder.meals.planner import plan_meals
from larder.models import InventoryItem

TODAY = date(2026, 11, 13)


def _vitals(hr: int = 72, resp: int = 14) -> Vitals:
    return Vitals(
        captured_at=datetime(2026, 11, 13, 12, tzinfo=timezone.utc),
        heart_rate_bpm=hr,
        spo2_percent=98,
        stress=30,
        respiration_per_min=resp,
    )


def _item(item_id: str, category: str, days: int) -> InventoryItem:
    return InventoryItem(
        id=item_id, name=item_id, category=category, quantity=1, unit="count",
        acquired_on=TODAY, expires_on=TODAY + timedelta(days=days),
    )


def test_resting_vitals_add_no_needs() -> None:
    assert body_needs(_vitals()) == []
    assert body_needs(None) == []
    assert "at rest" in body_note(_vitals())


def test_exertion_asks_for_staples_and_protein() -> None:
    assert body_needs(_vitals(hr=118)) == ["calorie staples", "protein"]
    assert body_needs(_vitals(resp=24)) == ["calorie staples", "protein"]
    assert "working hard" in body_note(_vitals(hr=118))


def test_exertion_reorders_the_meal_plan() -> None:
    items = [_item("lettuce", "leafy_greens", 1), _item("chicken", "meat", 2)]
    # Fresh food is short on the shelf, so at rest the greens go first.
    rest = plan_meals(items, today=TODAY, needs=survival_needs(items, None, _vitals(), today=TODAY))
    assert rest.meals[0].item_ids[0] == "lettuce"
    # Working hard: protein is now a need too; both fill a need, so soonest wins...
    hard = survival_needs(items, None, _vitals(hr=120), today=TODAY)
    assert "protein" in hard
    # ...but with greens not short (body demand only), the protein meal leads.
    body_only = plan_meals(items, today=TODAY, needs=body_needs(_vitals(hr=120)))
    assert body_only.meals[0].item_ids[0] == "chicken"
    assert "protein" in body_only.meals[0].why


def test_sample_wearable_reading_loads() -> None:
    assert try_load_vitals() is not None
