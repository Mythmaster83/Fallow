"""The full loop: plant, harvest, store, cook, compost, and feed the soil."""

from datetime import date, timedelta
from pathlib import Path

import pytest

from larder.grow.advisor import soil_notes
from larder.lifecycle import (
    COMPOST_DAYS,
    InvalidTransition,
    advance,
    compost_ready_on,
    harvest,
    move,
    next_states,
    plant,
)
from larder.meals.planner import plan_meals
from larder.models import InventoryItem
from larder.spoilage.predictor import heuristic_risks
from larder.store import InventoryStore

TODAY = date(2026, 11, 13)


def _food(
    item_id: str = "carrots",
    name: str = "carrots",
    category: str = "produce",
    *,
    location: str = "fridge",
    expires_on: date | None = None,
    quantity: float = 6,
) -> InventoryItem:
    return InventoryItem(
        id=item_id,
        name=name,
        category=category,
        quantity=quantity,
        unit="count",
        acquired_on=TODAY,
        expires_on=expires_on,
        location=location,
    )


def test_illegal_step_is_refused() -> None:
    with pytest.raises(InvalidTransition):
        advance(_food(), "compost", TODAY)
    with pytest.raises(InvalidTransition):
        advance(_food().model_copy(update={"state": "applied"}), "seed", TODAY)


def test_next_states_follow_the_graph() -> None:
    assert next_states(_food()) == ["opened", "cooked", "consumed", "trashed"]
    assert next_states(_food().model_copy(update={"state": "scraps"})) == ["compost"]


def test_freezing_extends_and_label_still_caps_the_fridge() -> None:
    chicken = _food("chicken", "chicken", "meat", expires_on=TODAY + timedelta(days=1))
    frozen = move(chicken, "freezer", TODAY).items[0]
    assert frozen.expires_on == TODAY + timedelta(days=90)

    # Moving labelled food around ordinary storage never pushes the label back.
    counter = _food("milk", "milk", "dairy", location="counter", expires_on=TODAY + timedelta(days=2))
    assert move(counter, "fridge", TODAY).items[0].expires_on == TODAY + timedelta(days=2)


def test_root_cellar_doubles_produce() -> None:
    cellar = move(_food(), "root cellar", TODAY).items[0]
    assert cellar.expires_on == TODAY + timedelta(days=42)


def test_cooking_resets_the_clock_and_leaves_scraps() -> None:
    step = advance(_food(), "cooked", TODAY)
    cooked, scraps = step.items
    assert cooked.state == "cooked"
    assert cooked.expires_on == TODAY + timedelta(days=4)
    assert scraps.state == "scraps"
    assert scraps.parent_id == "carrots"
    assert scraps.quantity == pytest.approx(1.2)
    assert [e.to_state for e in step.events] == ["cooked", "scraps"]


def test_non_food_is_left_out_of_spoilage_and_meals() -> None:
    items = [
        _food("spinach", "spinach", "leafy_greens", expires_on=TODAY),
        _food("pile", "kitchen compost", "scraps").model_copy(update={"state": "compost"}),
        _food("beds", "garlic", "produce").model_copy(update={"state": "growing"}),
    ]
    assert [r.item_id for r in heuristic_risks(items, today=TODAY)] == ["spinach"]
    plan = plan_meals(items, today=TODAY)
    assert {i for meal in plan.meals for i in meal.item_ids} == {"spinach"}


def test_full_loop_from_soil_back_to_soil() -> None:
    amendment = _food("leaf-mould", "leaf mould", "scraps").model_copy(
        update={"state": "soil_amendment", "location": "compost bin"}
    )
    sown = plant("kale", TODAY, amendment=amendment, item_id="kale-bed")
    by_id = {i.id: i for i in sown.items}
    assert by_id["kale-bed"].state == "growing"
    assert by_id["kale-bed"].location == "ground"
    assert by_id["leaf-mould"].state == "applied"

    picked = harvest(by_id["kale-bed"], TODAY + timedelta(days=50), quantity=2, unit="bunch")
    kale = picked.items[0]
    assert kale.state == "raw" and kale.is_food
    assert [e.to_state for e in picked.events] == ["harvested", "raw"]

    later = TODAY + timedelta(days=52)
    cooked, scraps = advance(kale, "cooked", later).items
    eaten = advance(cooked, "consumed", later).items[0]
    assert not eaten.is_food

    pile = advance(scraps, "compost", later).items[0]
    assert compost_ready_on(pile) == later + timedelta(days=COMPOST_DAYS)
    finished = advance(pile, "soil_amendment", later + timedelta(days=COMPOST_DAYS)).items[0]
    replanted = plant("garlic", later + timedelta(days=COMPOST_DAYS), amendment=finished)
    assert any(i.state == "applied" and i.id == finished.id for i in replanted.items)


def test_soil_notes_report_finished_and_ready_compost() -> None:
    finished = _food("lm", "leaf mould", "scraps", quantity=2).model_copy(update={"state": "soil_amendment"})
    pile = _food("kc", "kitchen compost", "scraps").model_copy(
        update={"state": "compost", "state_since": TODAY - timedelta(days=COMPOST_DAYS)}
    )
    notes = soil_notes([finished, pile], TODAY)
    assert "leaf mould" in notes
    assert "ready to screen" in notes


def test_store_saves_items_and_events(tmp_path: Path) -> None:
    store = InventoryStore(tmp_path / "t.db")
    store.upsert(_food())
    store.save(advance(_food(), "cooked", TODAY))
    assert store.get("carrots") is not None
    assert store.get("carrots-scraps") is not None
    events = store.list_events()
    assert [e.to_state for e in events] == ["scraps", "cooked"]  # newest first


def test_reset_restores_the_sample_and_clears_history(tmp_path: Path) -> None:
    from larder.store import default_inventory_fixture, load_inventory_fixture

    store = InventoryStore(tmp_path / "t.db")
    store.seed_from_fixture(default_inventory_fixture())
    spinach = store.get("spinach")
    assert spinach is not None
    store.save(advance(spinach, "cooked", TODAY))
    store.upsert(_food("extra", "extra", "produce"))
    store.reset()
    sample = load_inventory_fixture(default_inventory_fixture())
    assert {i.id for i in store.list_items()} == {i.id for i in sample}
    restored = store.get("spinach")
    assert restored is not None and restored.state == "raw"
    assert store.list_events() == []
