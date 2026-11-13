from datetime import date

from larder.health.nutrition import nutrition_report
from larder.meals.planner import plan_meals
from larder.meals.recipes import cook, recipe_for
from larder.store import load_inventory_fixture, default_inventory_fixture

TODAY = date(2026, 11, 13)


def _items():
    return load_inventory_fixture(default_inventory_fixture())


def test_recipes_only_use_inventory_food():
    items = _items()
    ids = {item.id for item in items}
    plan = plan_meals(items, today=TODAY)
    assert plan.meals
    for meal in plan.meals:
        recipe = recipe_for(meal, items)
        assert recipe.steps
        assert {i.item_id for i in recipe.ingredients} <= ids


def test_cooking_uses_up_the_urgent_food_and_one_staple_portion():
    items = _items()
    by_id = {item.id: item for item in items}
    meal = plan_meals(items, today=TODAY).meals[0]
    recipe = recipe_for(meal, items)
    changed = {item.id: item for item in cook(recipe, items)}
    main = recipe.ingredients[0].item_id
    assert changed[main].quantity == 0
    for ingredient in recipe.ingredients[1:]:
        assert 0 <= changed[ingredient.item_id].quantity < by_id[ingredient.item_id].quantity


def test_nutrition_report_grades_each_group():
    report = nutrition_report(_items(), today=TODAY)
    status = {g.group: g.status for g in report.groups}
    assert status["calorie staples"] == "covered"
    assert status["protein"] == "covered"  # canned beans last past the window
    assert status["fresh food"] in {"short", "covered"}
    assert report.covered == sum(1 for g in report.groups if g.status == "covered")
