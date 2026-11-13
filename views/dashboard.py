"""Dashboard: what spoils first, what to cook, and what to plant."""

from __future__ import annotations

import os

import streamlit as st

import fallow_ui as ui
from larder.grow.advisor import build_grow_plan
from larder.llm.client import LLMClient
from larder.meals.planner import plan_meals
from larder.sensors import current_sensor
from larder.sensors.base import LiveSensorUnavailable
from larder.spoilage.predictor import predict_spoilage
from larder.store import open_store
from pydantic import ValidationError

store = open_store()
items = store.list_items()
risks = predict_spoilage(items, client=LLMClient.from_env())
plan = plan_meals(items, risks=risks)

snapshot = None
sensor_error = None
try:
    snapshot = current_sensor().read()
except (LiveSensorUnavailable, ValueError, ValidationError, FileNotFoundError, OSError) as exc:
    sensor_error = str(exc)
grow = build_grow_plan(snapshot, items, risks=risks) if snapshot else None

sensor_mode = os.environ.get("SENSOR_MODE", "mock").strip().lower() or "mock"
ui.hero(
    "Nothing rots, nothing is wasted, everything is planned.",
    [("today", ui.today_label()), ("sensor", sensor_mode), ("spoilage", ui.source_note(risks))],
)

at_risk = sum(1 for r in risks if r.risk in ("critical", "high"))
plant_now = sum(1 for c in grow.crops if c.action == "plant now") if grow else 0
ui.kpis(
    [
        (str(len(items)), "items on hand", ""),
        (str(at_risk), "spoil within 2 days", "alert" if at_risk else "good"),
        (str(len(plan.meals)), f"meals planned, next {plan.horizon_days} days", ""),
        (str(plant_now), "crops to plant now", "good" if plant_now else ""),
    ]
)

left, right = st.columns([1.1, 1], gap="large")

with left:
    ui.section("What spoils first")
    if risks:
        ui.risk_list(risks, limit=6)
        if len(risks) > 6:
            st.page_link("views/pantry.py", label=f"See all {len(risks)} items in the pantry", icon=":material/arrow_forward:")
    else:
        ui.empty("The pantry is empty. Add food on the Pantry page.")

with right:
    ui.section("Cook this")
    if plan.meals:
        st.markdown(plan.summary)
        ui.meal_list(plan)
    else:
        ui.empty(plan.summary)

ui.section("Plant against the next gap")
if grow and snapshot:
    ui.conditions(snapshot)
    st.write("")
    ui.balance(grow)
    st.write("")
    ui.crop_grid(grow)
else:
    st.warning(sensor_error or "No sensor reading.")
