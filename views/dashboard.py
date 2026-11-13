"""Dashboard: what spoils first, what to cook, and what to plant."""

from __future__ import annotations

import os
from html import escape

import streamlit as st
from pydantic import ValidationError

import fallow_ui as ui
from larder.grow.advisor import build_grow_plan
from larder.achievements import ProgressStore
from larder.health.nutrition import nutrition_report
from larder.health.vitals import read_body_sample
from larder.llm.client import LLMClient
from larder.meals.planner import plan_meals
from larder.sensors import current_sensor
from larder.sensors.base import LiveSensorUnavailable
from larder.spoilage.predictor import predict_spoilage
from larder.store import default_db_path, open_store

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

ui.top(ui.greeting(), f"{ui.today_label()} · spoilage from {ui.source_note(risks)}", search=True)

# Dark feature card: the one thing to do next.
if plan.meals and risks:
    first = plan.meals[0]
    lead = risks[0]
    when = ui.days_short(lead.days_remaining).lower()
    title = f"{lead.item_name.capitalize()} {'expires today' if when == 'today' else 'has ' + when + ' left'}"
    ui.feature("Cook first", title, f"Day {first.day}: {first.name}.", "Open the recipe", "recipes", "skillet")
elif not items:
    ui.feature("Get started", "Your pantry is empty", "Add what you have and Fallow plans what to cook first.", "Add food", "pantry", "kitchen")
else:
    ui.feature("All clear", "Nothing is close to spoiling", plan.summary, "Open pantry", "pantry", "verified")

report = nutrition_report(items, risks=risks)
try:
    body = read_body_sample()
except (OSError, ValueError, ValidationError):
    body = None
ui.heading("Today", "Health details", "health")
if snapshot:
    ui.duo(ui.weather_card(snapshot, sensor_mode), ui.health_card(body, report))
else:
    ui.duo(f'<div class="fw-empty">{escape(sensor_error or "No weather reading.")}</div>', ui.health_card(body, report))

st.write("")
ui.cycle_card(ProgressStore().load())

at_risk = sum(1 for r in risks if r.risk in ("critical", "high"))
plant_now = sum(1 for c in grow.crops if c.action == "plant now") if grow else 0
ui.heading("Your kitchen", "View all", "pantry")
ui.stats(
    [
        ("kitchen", "peach", str(len(items)), "Items on hand"),
        ("timer", "lav", str(at_risk), "Spoil within 2 days"),
        ("skillet", "lime", str(len(plan.meals)), f"Meals, next {plan.horizon_days} days"),
        ("potted_plant", "cream", str(plant_now), "Crops to plant"),
    ]
)

left, right = st.columns(2, gap="medium")
with left:
    ui.heading("Spoilage")
    if risks:
        ui.days_chart(risks)
    else:
        ui.empty("Add food to see what spoils first.")
with right:
    ui.heading("Cook this", "Recipes", "recipes", anchor="cook-this")
    if plan.meals:
        ui.meal_rows(plan)
    else:
        ui.empty(plan.summary)

ui.heading("What spoils first", "See all" if len(risks) > 5 else None, "pantry")
if risks:
    ui.risk_rows(risks, items, limit=5)
else:
    ui.empty("The pantry is empty. Add food on the Pantry page.")

ui.heading("Plant against the next gap", "Soil & farm", "farm")
if grow and snapshot:
    ui.balance(grow)
    st.write("")
    ui.crop_rows(grow)
else:
    st.warning(sensor_error or "No sensor reading.")


def _reset_demo() -> None:
    """Back to the sample pantry and zero progress, for rehearsing the pitch."""
    default_db_path().unlink(missing_ok=True)
    st.session_state.pop("fw_reward", None)


st.write("")
st.button("Reset demo data", icon=":material/restart_alt:", type="tertiary", on_click=_reset_demo)
