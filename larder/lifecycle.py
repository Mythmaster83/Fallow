"""The dirt-to-plate-and-back state machine.

    seed → growing → harvested → raw → opened → cooked → consumed / trashed
                                                              ↓
                                  compost ← scraps ←──────────┘
                                     ↓
                               soil_amendment → applied (feeds the next planting)

Every function here is pure: it takes items and returns a ``Transition``
(rows to save, events to log). The pages persist the result. Each step
recalculates ``expires_on`` from the new state and storage location, so the
spoilage ranking moves the moment you freeze, open, or cook something.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

from larder.models import (
    CycleEvent,
    FOOD_STATES,
    InventoryItem,
    LifecycleState,
    Transition,
)
from larder.spoilage.shelf_life import baseline_days

TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    "seed": frozenset({"growing"}),
    "growing": frozenset({"harvested", "scraps"}),
    "harvested": frozenset({"raw"}),
    "raw": frozenset({"opened", "cooked", "consumed", "trashed"}),
    "opened": frozenset({"cooked", "consumed", "trashed"}),
    "cooked": frozenset({"consumed", "trashed"}),
    "consumed": frozenset({"scraps"}),
    "trashed": frozenset({"scraps"}),
    "scraps": frozenset({"compost"}),
    "compost": frozenset({"soil_amendment"}),
    "soil_amendment": frozenset({"applied"}),
    "applied": frozenset(),
}

# Where a thing goes by default when it enters a state.
_DEFAULT_LOCATION: dict[LifecycleState, str] = {
    "seed": "pantry",
    "growing": "ground",
    "harvested": "counter",
    "scraps": "compost bin",
    "compost": "compost bin",
    "soil_amendment": "compost bin",
    "applied": "ground",
}
_NOT_KITCHEN = {"ground", "compost bin"}

# Share of an item left as trimmings when it is cooked.
_SCRAP_FRACTION: dict[str, float] = {
    "leafy_greens": 0.1,
    "produce": 0.2,
    "berries": 0.05,
    "herb": 0.2,
    "meat": 0.15,
    "fish": 0.3,
    "eggs": 0.1,
}

# Crops the grow advisor can suggest, mapped to inventory categories.
CROP_CATEGORY: dict[str, str] = {
    "kale": "leafy_greens",
    "spinach": "leafy_greens",
    "chard": "leafy_greens",
    "garlic": "produce",
    "potatoes": "produce",
    "radishes": "produce",
    "peas": "produce",
    "bush beans": "produce",
    "thyme": "herb",
}

COOKED_DAYS = 4
OPENED_CAP_DAYS = 5
FREEZER_MIN_DAYS = 90
COMPOST_DAYS = 60
_RAW_FAMILY = {"harvested", "raw", "opened"}


class InvalidTransition(ValueError):
    """The requested step is not an edge in the lifecycle graph."""


def can_transition(from_state: LifecycleState, to_state: LifecycleState) -> bool:
    return to_state in TRANSITIONS[from_state]


def next_states(item: InventoryItem) -> list[LifecycleState]:
    """Legal next states for this item, in a stable display order."""
    order = list(TRANSITIONS)
    return sorted(TRANSITIONS[item.state], key=order.index)


def shelf_days(
    name: str,
    category: str,
    state: LifecycleState,
    location: str,
) -> int | None:
    """Days this food keeps in this state and place. ``None`` for non-food."""
    if state not in FOOD_STATES:
        return None
    if state == "cooked":
        return {"freezer": FREEZER_MIN_DAYS, "counter": 1}.get(location, COOKED_DAYS)
    days = baseline_days(name, category)
    if state == "opened":
        days = min(days, OPENED_CAP_DAYS)
    if location == "freezer":
        return max(days, FREEZER_MIN_DAYS)
    if location == "counter" and days < 30:
        return max(1, days // 2)
    if location == "root cellar" and category == "produce":
        return days * 2
    return days


def recalc_expiry(
    item: InventoryItem,
    to_state: LifecycleState,
    to_location: str,
    today: date,
) -> date | None:
    """New expiry after a state or storage change.

    A printed date still caps raw food in ordinary storage: moving milk from
    the counter to the fridge does not push its label back. Freezing, thawing,
    and cooking start a fresh clock.
    """
    days = shelf_days(item.name, item.category, to_state, to_location)
    if days is None:
        return None
    fresh = today + timedelta(days=days)
    keeps_label = (
        item.expires_on is not None
        and item.state in _RAW_FAMILY
        and to_state in _RAW_FAMILY
        and item.location != "freezer"
        and to_location != "freezer"
    )
    if keeps_label and item.expires_on is not None and item.expires_on < fresh:
        return item.expires_on
    return fresh


def advance(
    item: InventoryItem,
    to_state: LifecycleState,
    today: date,
    location: str | None = None,
    note: str = "",
) -> Transition:
    """Move one item to its next lifecycle state.

    Cooking also produces a scraps item for the compost, sized by category.
    """
    if not can_transition(item.state, to_state):
        allowed = ", ".join(next_states(item)) or "nothing (end of the line)"
        raise InvalidTransition(
            f"{item.name} is {item.state}; it can go to {allowed}, not {to_state}."
        )
    where = location or _default_location(item, to_state)
    updated = item.model_copy(
        update={
            "state": to_state,
            "state_since": today,
            "location": where,
            "expires_on": recalc_expiry(item, to_state, where, today),
        }
    )
    items = [updated]
    events = [_event(item, item.state, to_state, where, today, note)]
    if to_state == "cooked":
        scraps = _scraps_from(item, today)
        if scraps is not None:
            items.append(scraps)
            events.append(
                _event(scraps, None, "scraps", scraps.location, today, f"trimmings from cooking {item.name}")
            )
    return Transition(items=items, events=events)


def move(item: InventoryItem, location: str, today: date) -> Transition:
    """Change where an item is stored. The state stays; expiry is recalculated."""
    updated = item.model_copy(
        update={
            "location": location,
            "expires_on": recalc_expiry(item, item.state, location, today),
        }
    )
    note = f"moved {item.location} → {location}"
    return Transition(
        items=[updated],
        events=[_event(item, item.state, item.state, location, today, note)],
    )


def plant(
    crop: str,
    today: date,
    quantity: float = 1,
    unit: str = "bed",
    amendment: InventoryItem | None = None,
    item_id: str | None = None,
) -> Transition:
    """Put a crop in the ground. Optionally dig in finished compost first.

    This is where the loop closes: soil amendment → applied → new planting.
    """
    if amendment is not None and amendment.state != "soil_amendment":
        raise InvalidTransition(f"{amendment.name} is {amendment.state}, not finished soil amendment.")
    seed = InventoryItem(
        id=item_id or f"{_slug(crop)}-{uuid.uuid4().hex[:4]}",
        name=crop,
        category=CROP_CATEGORY.get(crop.lower(), "produce"),
        quantity=quantity,
        unit=unit,
        acquired_on=today,
        location="pantry",
        state="seed",
        state_since=today,
    )
    note = f"planted into ground amended with {amendment.name}" if amendment else "planted"
    sown = advance(seed, "growing", today, note=note)
    items = list(sown.items)
    events = [_event(seed, None, "seed", "pantry", today, "seed on hand"), *sown.events]
    if amendment is not None:
        applied = advance(amendment, "applied", today, note=f"dug into the {crop} bed")
        items.extend(applied.items)
        events = [*applied.events, *events]
    return Transition(items=items, events=events)


def harvest(
    item: InventoryItem,
    today: date,
    quantity: float,
    unit: str,
    location: str = "fridge",
) -> Transition:
    """Pick a growing crop and store it: growing → harvested → raw."""
    if item.state != "growing":
        raise InvalidTransition(f"{item.name} is {item.state}; only growing crops can be harvested.")
    picked = advance(
        item.model_copy(update={"quantity": quantity, "unit": unit, "acquired_on": today}),
        "harvested",
        today,
        location="counter",
        note=f"picked {quantity:g} {unit}",
    )
    stored = advance(picked.items[0], "raw", today, location=location, note=f"stored in {location}")
    return Transition(items=stored.items, events=[*picked.events, *stored.events])


def compost_ready_on(item: InventoryItem) -> date | None:
    """When an active compost pile should be finished."""
    if item.state != "compost":
        return None
    start = item.state_since or item.acquired_on
    return start + timedelta(days=COMPOST_DAYS)


def _default_location(item: InventoryItem, to_state: LifecycleState) -> str:
    if to_state in _DEFAULT_LOCATION:
        return _DEFAULT_LOCATION[to_state]
    if item.location in _NOT_KITCHEN:
        return "fridge"
    return item.location


def _scraps_from(item: InventoryItem, today: date) -> InventoryItem | None:
    fraction = _SCRAP_FRACTION.get(item.category)
    if fraction is None:
        return None
    amount = round(item.quantity * fraction, 2)
    if amount <= 0:
        return None
    return InventoryItem(
        id=f"{item.id}-scraps",
        name=f"{item.name} scraps",
        category="scraps",
        quantity=amount,
        unit=item.unit,
        acquired_on=today,
        location="compost bin",
        state="scraps",
        state_since=today,
        parent_id=item.id,
    )


def _event(
    item: InventoryItem,
    from_state: LifecycleState | None,
    to_state: LifecycleState,
    location: str,
    today: date,
    note: str,
) -> CycleEvent:
    return CycleEvent(
        item_id=item.id,
        item_name=item.name,
        from_state=from_state,
        to_state=to_state,
        location=location,
        on=today,
        note=note,
    )


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "item"
