"""The full loop: plant, harvest, store, cook, compost, and feed the soil."""

from __future__ import annotations

from collections import Counter
from datetime import date
from html import escape

import streamlit as st

import fallow_ui as ui
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
from larder.models import FOOD_STATES, STORAGE_LOCATIONS, Transition
from larder.sensors import current_sensor
from larder.sensors.base import LiveSensorUnavailable
from larder.store import open_store

load_project_env()

ui.top(
    "Cycle",
    "Dirt to plate and back. Each step updates a real pantry row and its expiry.",
    avatar_icon="compost",
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

# --- The loop: three phases, each stage with its live count --------------------
PHASES = [
    ("Grow", "potted_plant", ["seed", "growing", "harvested"]),
    ("Kitchen", "skillet", ["raw", "opened", "cooked", "consumed", "trashed"]),
    ("Return", "compost", ["scraps", "compost", "soil_amendment", "applied"]),
]
STAGE_ICON = {
    "seed": "grain", "growing": "potted_plant", "harvested": "agriculture",
    "raw": "nutrition", "opened": "lunch_dining", "cooked": "skillet", "consumed": "restaurant", "trashed": "delete",
    "scraps": "recycling", "compost": "compost", "soil_amendment": "landscape", "applied": "grass",
}
counts = Counter(item.state for item in items if item.quantity > 0)


def _phase(name: str, glyph: str, states: list[str]) -> str:
    total = sum(counts.get(s, 0) for s in states)
    rows = "".join(
        f'<div class="fw-stage{" on" if counts.get(s, 0) else ""}">{ui.icon(STAGE_ICON[s], 18)}'
        f'<span>{escape(_label(s).capitalize())}</span><b>{counts.get(s, 0)}</b></div>'
        for s in states
    )
    return (
        f'<div class="fw-phase"><div class="ph-head"><div class="fw-tile">{ui.icon(glyph)}</div>'
        f'<div><div class="ph-name">{escape(name)}</div><div class="ph-sub">{total} item{"s" if total != 1 else ""} here</div></div></div>'
        f'<div class="ph-stages">{rows}</div></div>'
    )


arrow = f'<div class="fw-loop-arrow">{ui.icon("arrow_forward", 22)}</div>'
st.html(
    '<div class="fw-loop">'
    + arrow.join(_phase(*phase) for phase in PHASES)
    + f'</div><div class="fw-return">{ui.icon("u_turn_left", 18)}Finished compost feeds the next bed, and the loop starts again.</div>'
)

# --- Actions ------------------------------------------------------------------
ui.heading("Take a step")
ACTIONS = {
    "step": ":material/arrow_forward: Next step",
    "plant": ":material/potted_plant: Plant",
    "harvest": ":material/agriculture: Harvest",
    "store": ":material/swap_horiz: Store elsewhere",
}
with st.container(key="card-cycle-actions"):
    action = st.segmented_control(
        "Action", list(ACTIONS), format_func=ACTIONS.get, default="step", key="cycle_action", label_visibility="collapsed"
    ) or "step"

    if action == "step":
        movable = [item for item in items if next_states(item) and item.quantity > 0]
        if not movable:
            st.caption("Nothing can move right now.")
        else:
            by_id = {i.id: i for i in movable}
            choice = by_id[
                st.selectbox(
                    "Item",
                    list(by_id),
                    format_func=lambda k: f"{by_id[k].name} — {_label(by_id[k].state)} ({by_id[k].location})",
                    key="step_item_id",
                )
            ]
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

    if action == "plant":
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
        amend_by_id = {i.id: i for i in amendments}
        amend_id = st.selectbox(
            "Dig in first",
            ["", *amend_by_id],
            format_func=lambda k: "nothing" if not k else f"{amend_by_id[k].name} ({amend_by_id[k].quantity:g} {amend_by_id[k].unit})",
            index=1 if amendments else 0,
            key="plant_amendment_id",
        )
        amendment = amend_by_id.get(amend_id or "")
        if st.button("Plant", type="primary", key="plant_go"):
            step = plant(str(crop), today, amendment=amendment)
            fed = f" into ground fed with {amendment.name}" if amendment else ""
            _commit(step, f"Planted {crop}{fed}.")

    if action == "harvest":
        growing = [item for item in items if item.state == "growing"]
        if not growing:
            st.caption("Nothing is growing. Plant something first.")
        else:
            beds = {i.id: i for i in growing}
            bed = beds[
                st.selectbox(
                    "Bed",
                    list(beds),
                    format_func=lambda k: f"{beds[k].name} (in since {(beds[k].state_since or beds[k].acquired_on).isoformat()})",
                    key="harvest_bed_id",
                )
            ]
            left, mid, right = st.columns(3)
            qty = left.number_input("Quantity", min_value=0.5, value=2.0, step=0.5, key="harvest_qty")
            unit = mid.text_input("Unit", value="bunch", key="harvest_unit")
            where = right.selectbox("Store in", ["fridge", "root cellar", "pantry", "counter", "freezer"], key="harvest_where")
            if st.button("Harvest", type="primary", key="harvest_go"):
                step = harvest(bed, today, quantity=float(qty), unit=unit.strip() or "count", location=str(where))
                _commit(step, f"Harvested {qty:g} {unit} of {bed.name} into the {where}. It is in the pantry ranking now.")

    if action == "store":
        food = [item for item in items if item.is_food]
        if not food:
            st.caption("No food on hand.")
        else:
            food_by_id = {i.id: i for i in food}
            thing = food_by_id[
                st.selectbox(
                    "Food",
                    list(food_by_id),
                    format_func=lambda k: f"{food_by_id[k].name} ({food_by_id[k].location}, expires "
                    f"{food_by_id[k].expires_on.isoformat() if food_by_id[k].expires_on else 'unknown'})",
                    key="store_item_id",
                )
            ]
            spots = [loc for loc in STORAGE_LOCATIONS if loc not in {"ground", "compost bin", thing.location}]
            dest = st.radio("Move to", spots, horizontal=True, key=f"store_dest_{thing.id}")
            if st.button("Move", type="primary", key="store_go"):
                step = move(thing, str(dest), today)
                new = step.items[0].expires_on
                _commit(step, f"{thing.name} moved to the {dest}; now good until {new.isoformat() if new else 'unknown'}.")

# --- Garden and compost -----------------------------------------------------------
ui.heading("Garden and compost")
outside = [item for item in items if item.state not in FOOD_STATES and item.state not in {"consumed", "applied"}]
if outside:
    rows = []
    for item in outside:
        since = item.state_since or item.acquired_on
        ready = compost_ready_on(item)
        if ready:
            span = max(1, (ready - since).days)
            pct = min(100, max(0, (today - since).days / span * 100))
            right = (
                f'<div class="fw-prog"><div class="lbl">{"Ready now" if pct >= 100 else f"Ready {ready:%b} {ready.day}"}</div>'
                f'<div class="bar"><i style="width:{pct:.0f}%"></i></div></div>'
            )
        else:
            right = f'<span class="fw-pill ghost">since {since:%b} {since.day}</span>'
        rows.append(
            f'<div class="fw-row"><div class="fw-tile">{ui.icon(STAGE_ICON.get(item.state, "eco"))}</div>'
            f'<div class="main"><div class="name">{escape(item.name)}</div>'
            f'<div class="small">{escape(_label(item.state))} · {escape(item.location)} · {item.quantity:g} {escape(item.unit)}</div></div>{right}</div>'
        )
    st.html(f'<div class="fw-rows">{"".join(rows)}</div>')
else:
    ui.empty("Nothing in the garden or compost yet. Plant something or cook a meal to start the loop.")

ui.heading("History")
events = store.list_events(limit=30)
if events:
    rows = []
    for event in events:
        if event.from_state == event.to_state:  # a storage move, not a stage change
            what = f"Moved to the {escape(event.location)}"
        else:
            frm = _label(event.from_state).capitalize() if event.from_state else "New"
            what = f"{escape(frm)} → {escape(_label(event.to_state))} · {escape(event.location)}"
        note = f" · {escape(event.note)}" if event.note else ""
        rows.append(
            f'<div class="fw-row fw-tl"><div class="when"><b>{event.on.day}</b><span>{event.on:%b}</span></div>'
            f'<div class="fw-tile">{ui.icon(STAGE_ICON.get(event.to_state, "sync_alt"))}</div>'
            f'<div class="main"><div class="name">{escape(event.item_name)}</div>'
            f'<div class="small">{what}{note}</div></div></div>'
        )
    st.html(f'<div class="fw-rows">{"".join(rows)}</div>')
else:
    ui.empty("No steps taken yet. Use Take a step above.")


with st.expander("Demo tools"):
    st.caption("Put the pantry, garden, and compost back to the sample data and clear the history.")
    if st.button("Reset demo data", icon=":material/restart_alt:", key="reset_demo"):
        store.reset()
        st.session_state["cycle_flash"] = "Reset to the sample data. History cleared."
        st.rerun()
