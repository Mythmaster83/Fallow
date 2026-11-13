"""The meal planner may only cook food that is already in the inventory."""

from datetime import date, timedelta

from larder.meals.planner import plan_meals
from larder.models import InventoryItem, SpoilageRisk

TODAY = date(2026, 11, 13)


def _item(
    item_id: str,
    name: str,
    category: str,
    *,
    expires_on: date | None = None,
    acquired_on: date | None = None,
    quantity: float = 1,
) -> InventoryItem:
    return InventoryItem(
        id=item_id,
        name=name,
        category=category,
        quantity=quantity,
        unit="count",
        acquired_on=acquired_on or TODAY,
        expires_on=expires_on,
        location="pantry",
    )


def _assert_inventory_only(plan, items: list[InventoryItem]) -> None:
    by_id = {item.id: item for item in items}
    assert set(plan.priority_item_ids) <= set(by_id)
    for meal in plan.meals:
        assert set(meal.item_ids) <= set(by_id)
        assert meal.uses == [by_id[item_id].name for item_id in meal.item_ids]


def test_meals_use_only_inventory_ids() -> None:
    items = [
        _item("spinach", "spinach", "leafy_greens", expires_on=TODAY + timedelta(days=1)),
        _item("rice", "rice", "grain", acquired_on=TODAY - timedelta(days=30)),
    ]
    plan = plan_meals(items, today=TODAY)
    _assert_inventory_only(plan, items)
    used = {item_id for meal in plan.meals for item_id in meal.item_ids}
    assert "spinach" in used
    assert "quinoa" not in used
    assert all("quinoa" not in name for meal in plan.meals for name in meal.uses)


def test_ghost_risk_cannot_add_a_food() -> None:
    items = [_item("rice", "rice", "grain")]
    ghost = SpoilageRisk(
        item_id="quinoa",
        item_name="quinoa",
        risk="critical",
        days_remaining=0,
        reason="not on hand",
        source="heuristic",
    )
    plan = plan_meals(items, risks=[ghost], today=TODAY)
    _assert_inventory_only(plan, items)
    blob = " ".join(meal.name for meal in plan.meals) + " " + plan.summary
    assert "quinoa" not in blob
    assert plan.meals == []


def test_empty_inventory() -> None:
    plan = plan_meals([], today=TODAY)
    assert plan.meals == []
    assert plan.priority_item_ids == []
    assert "empty" in plan.summary


def test_zero_quantity_is_ignored() -> None:
    items = [_item("spinach", "spinach", "leafy_greens", expires_on=TODAY, quantity=0)]
    plan = plan_meals(items, today=TODAY)
    assert plan.meals == []
    assert plan.priority_item_ids == []


def test_stable_food_does_not_get_a_meal() -> None:
    items = [_item("rice", "rice", "grain", acquired_on=TODAY)]
    plan = plan_meals(items, today=TODAY)
    assert plan.meals == []
    assert plan.priority_item_ids == []
    assert "close to spoiling" in plan.summary


def test_horizon_caps_meals_and_keeps_full_priority() -> None:
    items = [
        _item("yogurt", "yogurt", "dairy", expires_on=TODAY),
        _item("spinach", "spinach", "leafy_greens", expires_on=TODAY + timedelta(days=1)),
        _item("chicken", "chicken", "meat", expires_on=TODAY + timedelta(days=2)),
        _item("bread", "bread", "bread", expires_on=TODAY + timedelta(days=4)),
        _item("rice", "rice", "grain", acquired_on=TODAY - timedelta(days=5)),
    ]
    plan = plan_meals(items, horizon_days=2, today=TODAY)
    _assert_inventory_only(plan, items)
    assert len(plan.meals) == 2
    assert plan.priority_item_ids == ["yogurt", "spinach", "chicken", "bread"]
    assert plan.meals[0].item_ids[0] == "yogurt"
    assert "rice" in plan.meals[0].item_ids


def test_soonest_food_is_the_first_meal() -> None:
    items = [
        _item("apples", "apples", "produce", expires_on=TODAY + timedelta(days=4)),
        _item("salmon", "salmon", "fish", expires_on=TODAY),
    ]
    plan = plan_meals(items, today=TODAY)
    assert plan.meals[0].item_ids[0] == "salmon"
    assert plan.priority_item_ids[0] == "salmon"


def test_short_food_group_goes_first_within_the_same_urgency() -> None:
    items = [
        _item("bread", "bread", "bread", expires_on=TODAY + timedelta(days=1)),
        _item("chicken", "chicken", "meat", expires_on=TODAY + timedelta(days=2)),
        _item("rice", "rice", "grain", acquired_on=TODAY),
    ]
    plain = plan_meals(items, today=TODAY, needs=[])
    assert plain.meals[0].item_ids[0] == "bread"  # soonest first
    plan = plan_meals(items, today=TODAY, needs=["protein"])
    assert plan.meals[0].item_ids[0] == "chicken"
    assert "protein" in plan.meals[0].why
    _assert_inventory_only(plan, items)


def test_a_need_never_beats_a_worse_urgency_band() -> None:
    items = [
        _item("spinach", "spinach", "leafy_greens", expires_on=TODAY),
        _item("chicken", "chicken", "meat", expires_on=TODAY + timedelta(days=2)),
    ]
    plan = plan_meals(items, today=TODAY, needs=["protein"])
    assert plan.meals[0].item_ids[0] == "spinach"
