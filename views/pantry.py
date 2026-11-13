"""Pantry: everything on hand, with spoilage, plus add and remove."""

from __future__ import annotations

import re
import uuid
from datetime import date
from html import escape

import streamlit as st

import fallow_ui as ui
from larder.llm.client import LLMClient
from larder.models import FOOD_STATES, STORAGE_LOCATIONS, InventoryItem
from larder.spoilage.predictor import predict_spoilage
from larder.spoilage.shelf_life import CATEGORY_DAYS
from larder.store import open_store

LOCATIONS = [loc for loc in STORAGE_LOCATIONS if loc not in {"ground", "compost bin"}]

store = open_store()
items = [item for item in store.list_items() if item.state in FOOD_STATES]
risks = predict_spoilage(items, client=LLMClient.from_env())
risk_by_id = {r.item_id: r for r in risks}

ui.top("Pantry", f"{len(items)} items \u00b7 soonest to spoil first", avatar_icon="kitchen")

# A message set before a rerun, shown once after it.
flash = st.session_state.pop("pantry_flash", None)
if flash:
    st.success(flash, icon=":material/check_circle:")


def _add() -> None:
    s = st.session_state
    name = s.add_name.strip()
    unit = s.add_unit.strip()
    if not name:
        s.add_error = "Give the food a name."
        return
    if s.add_qty <= 0:
        s.add_error = "Quantity has to be greater than zero."
        return
    if not unit:
        s.add_error = "Give the quantity a unit, such as lb, bag, or count."
        return
    expires = s.get("add_expires") if s.add_knows_expiry else None
    if expires is not None and expires < s.add_acquired:
        s.add_error = "The expiry date can't be before the day you got it."
        return
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "item"
    store.upsert(
        InventoryItem(
            id=f"{slug}-{uuid.uuid4().hex[:4]}",
            name=name,
            category=s.add_category,
            quantity=float(s.add_qty),
            unit=unit,
            acquired_on=s.add_acquired,
            expires_on=expires,
            location=s.add_location,
        )
    )
    s.add_error = None
    s.pantry_flash = f"Added {name}."
    s.add_name = ""


def _remove(item_id: str, name: str) -> None:
    store.delete(item_id)
    st.session_state.pantry_flash = f"Removed {name}."


left, right = st.columns([1.6, 1], gap="large")

with left:
    ui.heading("On hand")
    where = st.segmented_control(
        "Where", ["all"] + LOCATIONS, default="all", label_visibility="collapsed"
    )
    query = st.text_input("Search", placeholder="Search food", label_visibility="collapsed")

    def _order(item: InventoryItem) -> tuple[int, str]:
        risk = risk_by_id.get(item.id)
        return (risk.days_remaining if risk else 10_000, item.name.lower())

    shown = [
        item
        for item in sorted(items, key=_order)
        if (not where or where == "all" or item.location == where)
        and (not query or query.lower() in item.name.lower())
    ]

    if not items:
        ui.empty("Nothing stored yet. Add the first item on the right.")
    elif not shown:
        ui.empty("No food matches that filter.")

    for row_start in range(0, len(shown), 2):
        cols = st.columns(2)
        for col, item in zip(cols, shown[row_start : row_start + 2]):
            risk = risk_by_id.get(item.id)
            with col.container(key=f"card-{item.id}"):
                ic, tone = ui.item_icon(item.category)
                if risk:
                    pill = f'<span class="fw-pill {ui.RISK_TONE[risk.risk]}">{escape(ui.days_short(risk.days_remaining))}</span>'
                else:
                    pill = '<span class="fw-pill ghost">used up</span>'
                expires = f"expires {item.expires_on:%b %d}" if item.expires_on else "no expiry date"
                meta = f"{item.quantity:g} {item.unit} \u00b7 {item.location} \u00b7 {item.state.replace('_', ' ')} \u00b7 {expires}"
                st.html(
                    f'<div class="fw-row" style="padding:0"><div class="fw-tile {tone}">{ui.icon(ic)}</div>'
                    f'<div class="main"><div class="name">{escape(item.name)}</div>'
                    f'<div class="small">{escape(meta)}</div></div>{pill}</div>'
                )
                st.button(
                    "Remove",
                    key=f"rm-{item.id}",
                    icon=":material/delete:",
                    type="tertiary",
                    on_click=_remove,
                    args=(item.id, item.name),
                )

with right:
    ui.heading("Add food")
    with st.container(key="addform"):
        st.text_input("Name", key="add_name", placeholder="strawberries")
        c1, c2 = st.columns(2)
        c1.selectbox(
            "Category",
            sorted(CATEGORY_DAYS),
            key="add_category",
            format_func=lambda c: c.replace("_", " "),
        )
        c2.selectbox("Where it is", LOCATIONS, key="add_location")
        c3, c4 = st.columns(2)
        c3.number_input("Quantity", min_value=0.0, value=1.0, step=0.5, key="add_qty")
        c4.text_input("Unit", value="count", key="add_unit")
        st.date_input("Got it on", value=date.today(), key="add_acquired")
        knows = st.toggle("I know the expiry date", key="add_knows_expiry")
        if knows:
            st.date_input("Expires on", value=date.today(), key="add_expires")
        else:
            st.caption("Fallow will estimate it from the shelf-life table.")
        if st.session_state.get("add_error"):
            st.error(st.session_state.add_error)
        st.button("Add to pantry", type="primary", icon=":material/add:", on_click=_add, width="stretch")
