"""The full loop: plant, harvest, store, cook, compost, and feed the soil."""

from __future__ import annotations

from collections import Counter
from datetime import date

import streamlit as st

from larder.grow.advisor import build_grow_plan
from larder.lifecycle import (
    CROP_CATEGORY,
    TRANSITIONS,
    InvalidTransition,
    advance,
    compost_ready_on,
    harvest,
    move,
    next_states,
    plant,
)
from larder.llm.client import load_project_env
from larder.models import FOOD_STATES, STORAGE_LOCATIONS, InventoryItem, Transition
from larder.sensors import current_sensor
from larder.sensors.base import LiveSensorUnavailable
from larder.store import open_store

load_project_env()
st.set_page_config(page_title="Cycle · Fallow", page_icon="♻️", layout="wide")

st.title("Cycle")
st.caption(
    "Dirt to plate and back. Every step moves a real inventory row and recalculates "
    "its expiry. Scraps from cooking go to the compost, and finished compost feeds the next bed."
)

store = open_store()
today = date.today()
items = store.list_items()


def _label(state: str) -> str:
    return state.replace("_", " ")


def _commit(step: Transition, message: str) -> None:
    store.save(step)
    st.session_state["cycle_flash"] = message
    st.rerun()


flash = st.session_state.pop("cycle_flash", None)
if flash:
    st.success(flash)

# --- The loop, with how many things sit in each state -----------------------
counts = Counter(item.state for item in items if item.quantity > 0)
nodes: list[str] = []
for state in TRANSITIONS:
    n = counts.get(state, 0)
    food = state in FOOD_STATES
    fill = ("#ff6b35" if food else "#4ecdc4") if n else "#2a2a2a"
    font = "#0a0a0a" if n else "#888888"
    nodes.append(
        f'"{state}" [label="{_label(state)}\\n{n}", style=filled, fillcolor="{fill}", '
        f'fontcolor="{font}", color="{fill}"]'
    )
edges = [f'"{a}" -> "{b}"' for a, outs in TRANSITIONS.items() for b in sorted(outs)]
edges.append('"applied" -> "seed" [style=dashed, label=" feeds the next bed"]')
dot = (
    "digraph cycle {\n"
    'bgcolor="transparent"; rankdir=LR; nodesep=0.3; ranksep=0.35;\n'
    'node [shape=box, style=rounded, fontname="Helvetica", fontsize=11];\n'
    'edge [color="#777777", fontcolor="#999999", fontsize=9];\n'
    + "\n".join(nodes + edges)
    + "\n}"
)
st.graphviz_chart(dot, width="stretch")
st.caption("Orange: food you can eat. Teal: the garden and compost side of the loop. The number is how many items sit there now.")

# --- Actions ------------------------------------------------------------------
step_tab, plant_tab, harvest_tab, store_tab = st.tabs(
    ["Next step", "Plant", "Harvest", "Store elsewhere"]
)

with step_tab:
    movable = [item for item in items if next_states(item) and item.quantity > 0]
    if not movable:
        st.caption("Nothing can move right now.")
    else:
        choice = st.selectbox(
            "Item",
            movable,
            format_func=lambda i: f"{i.name} — {_label(i.state)} ({i.location})",
            key="step_item",
        )
        assert isinstance(choice, InventoryItem)
        target = st.radio(
            "Move it to",
            next_states(choice),
            format_func=_label,
            horizontal=True,
            key=f"step_target_{choice.id}",
        )
        if target == "cooked":
            st.caption("Cooking also sends the trimmings to the compost as scraps.")
        if st.button("Do it", type="primary", key="step_go"):
            try:
                step = advance(choice, target, today)
            except InvalidTransition as exc:
                st.error(str(exc))
            else:
                extra = " Scraps went to the compost." if len(step.items) > 1 else ""
                _commit(step, f"{choice.name}: {_label(choice.state)} → {_label(target)}.{extra}")

with plant_tab:
    suggested: list[str] = []
    try:
        grow = build_grow_plan(current_sensor().read(), items)
        suggested = [crop.crop for crop in grow.crops if crop.action == "plant now"]
        if grow.soil_notes:
            st.info(grow.soil_notes)
    except (LiveSensorUnavailable, ValueError, FileNotFoundError, OSError) as exc:
        st.warning(f"No sensor reading, so every crop is listed. ({exc})")
    crops = suggested or sorted(CROP_CATEGORY)
    crop = st.selectbox("Crop (from the grow advisor)", crops, key="plant_crop")
    amendments = [item for item in items if item.state == "soil_amendment" and item.quantity > 0]
    amendment = st.selectbox(
        "Dig in first",
        [None, *amendments],
        format_func=lambda i: "nothing" if i is None else f"{i.name} ({i.quantity:g} {i.unit})",
        index=1 if amendments else 0,
        key="plant_amendment",
    )
    if st.button("Plant", type="primary", key="plant_go"):
        step = plant(str(crop), today, amendment=amendment if isinstance(amendment, InventoryItem) else None)
        fed = f" into ground fed with {amendment.name}" if isinstance(amendment, InventoryItem) else ""
        _commit(step, f"Planted {crop}{fed}.")

with harvest_tab:
    growing = [item for item in items if item.state == "growing"]
    if not growing:
        st.caption("Nothing is growing. Plant something first.")
    else:
        bed = st.selectbox(
            "Bed",
            growing,
            format_func=lambda i: f"{i.name} (in since {(i.state_since or i.acquired_on).isoformat()})",
            key="harvest_bed",
        )
        assert isinstance(bed, InventoryItem)
        left, mid, right = st.columns(3)
        qty = left.number_input("Quantity", min_value=0.5, value=2.0, step=0.5, key="harvest_qty")
        unit = mid.text_input("Unit", value="bunch", key="harvest_unit")
        where = right.selectbox("Store in", ["fridge", "root cellar", "pantry", "counter", "freezer"], key="harvest_where")
        if st.button("Harvest", type="primary", key="harvest_go"):
            step = harvest(bed, today, quantity=float(qty), unit=unit.strip() or "count", location=str(where))
            _commit(step, f"Harvested {qty:g} {unit} of {bed.name} into the {where}. It is in the pantry ranking now.")

with store_tab:
    food = [item for item in items if item.is_food]
    if not food:
        st.caption("No food on hand.")
    else:
        thing = st.selectbox(
            "Food",
            food,
            format_func=lambda i: f"{i.name} ({i.location}, expires {i.expires_on.isoformat() if i.expires_on else 'unknown'})",
            key="store_item",
        )
        assert isinstance(thing, InventoryItem)
        spots = [loc for loc in STORAGE_LOCATIONS if loc not in {"ground", "compost bin", thing.location}]
        dest = st.radio("Move to", spots, horizontal=True, key=f"store_dest_{thing.id}")
        if st.button("Move", type="primary", key="store_go"):
            step = move(thing, str(dest), today)
            new = step.items[0].expires_on
            _commit(step, f"{thing.name} moved to the {dest}; now good until {new.isoformat() if new else 'unknown'}.")

# --- Garden and compost --------------------------------------------------------
st.subheader("Garden and compost")
outside = [item for item in items if item.state not in FOOD_STATES and item.state not in {"consumed", "applied"}]
if outside:
    st.dataframe(
        [
            {
                "item": item.name,
                "state": _label(item.state),
                "where": item.location,
                "amount": f"{item.quantity:g} {item.unit}",
                "since": (item.state_since or item.acquired_on).isoformat(),
                "ready": (r.isoformat() if (r := compost_ready_on(item)) else ""),
            }
            for item in outside
        ],
        width="stretch",
        hide_index=True,
    )
else:
    st.caption("Nothing in the garden or compost yet.")

st.subheader("History")
events = store.list_events(limit=30)
if events:
    st.dataframe(
        [
            {
                "on": event.on.isoformat(),
                "item": event.item_name,
                "step": f"{_label(event.from_state) if event.from_state else '—'} → {_label(event.to_state)}",
                "where": event.location,
                "note": event.note,
            }
            for event in events
        ],
        width="stretch",
        hide_index=True,
    )
else:
    st.caption("No steps taken yet. Use the tabs above.")
