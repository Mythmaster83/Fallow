from datetime import date

from larder.achievements import ProgressStore, record_cook, record_health_check, record_plant
from larder.grow.balance import find_gaps
from larder.meals.planner import plan_meals
from larder.meals.recipes import cook, recipe_for
from larder.models import GrowCrop
from larder.spoilage.predictor import heuristic_risks
from larder.store import default_inventory_fixture, load_inventory_fixture

TODAY = date(2026, 11, 13)


def test_full_cycle_unlocks_in_order(tmp_path):
    store = ProgressStore(tmp_path / "p.db")
    items = load_inventory_fixture(default_inventory_fixture())
    risks = heuristic_risks(items, today=TODAY)
    recipe = recipe_for(plan_meals(items, risks=risks).meals[0], items)
    changed = {i.id: i for i in cook(recipe, items)}
    after_items = [changed.get(i.id, i) for i in items]
    reward = record_cook(store, recipe, risks, heuristic_risks(after_items, today=TODAY))
    ids = {a.id for a in reward.unlocked}
    assert {"first_rescue", "last_minute"} <= ids  # spinach expires today
    assert reward.xp_after == reward.xp_before + reward.xp_gained > 0

    assert record_health_check(store).unlocked[0].id == "health_check"
    assert record_health_check(store) is None  # only once

    gaps = find_gaps(after_items, today=TODAY)
    reward = record_plant(store, GrowCrop(crop="kale", action="plant now", reason="", fills="fresh food"), gaps)
    ids = {a.id for a in reward.unlocked}
    assert {"green_thumb", "gap_closer", "full_cycle"} <= ids
    progress = store.load()
    assert all(progress.cycle) and progress.level >= 1
