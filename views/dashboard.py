"""Dashboard: what spoils first, what to cook, and what to plant."""

from __future__ import annotations

import streamlit as st
from pydantic import ValidationError

import fallow_ui as ui
from larder.grow.advisor import build_grow_plan
from larder.health.vitals import survival_needs, try_load_vitals
from larder.llm.client import LLMClient
from larder.meals.planner import plan_meals
from larder.sensors import current_sensor
from larder.sensors.base import LiveSensorUnavailable
from larder.sensors.warnings import condition_warnings
from larder.spoilage.predictor import predict_spoilage
from larder.store import open_store

store = open_store()
items = store.list_items()
risks = predict_spoilage(items, client=LLMClient.from_env())
vitals = try_load_vitals()
plan = plan_meals(items, risks=risks, needs=survival_needs(items, risks, vitals))

snapshot = None
sensor_error = None
try:
    snapshot = current_sensor().read()
except (LiveSensorUnavailable, ValueError, ValidationError, FileNotFoundError, OSError) as exc:
    sensor_error = str(exc)
grow = build_grow_plan(snapshot, items, risks=risks) if snapshot else None

ui.top(ui.greeting(), f"{ui.today_label()} · spoilage from {ui.source_note(risks)}")
ui.search_link("Search your pantry")

# Dark feature card: the one thing to do next.
if plan.meals and risks:
    first = plan.meals[0]
    lead = risks[0]
    when = ui.days_short(lead.days_remaining).lower()
    title = f"{lead.item_name.capitalize()} {'expires today' if when == 'today' else 'has ' + when + ' left'}"
    ui.feature("Cook first", title, f"Day {first.day}: {first.name}.", "Open the recipe", "recipes", "skillet")
elif not any(i.is_food for i in items):
    ui.feature("Get started", "Your pantry is empty", "Add what you have and Fallow plans what to cook first.", "Add food", "pantry", "kitchen")
else:
    ui.feature("All clear", "Nothing is close to spoiling", plan.summary, "Open pantry", "pantry", "verified")

ui.heading("Conditions")
ui.condition_banner(snapshot, vitals, condition_warnings(snapshot) if snapshot else ["No weather reading"])

plant_now = sum(1 for c in grow.crops if c.action == "plant now") if grow else 0
ui.heading("Your kitchen", "View all", "pantry")
ui.stats(
    [
        ("kitchen", "peach", str(sum(1 for i in items if i.is_food)), "Items on hand"),
        ("skillet", "lime", str(len(plan.meals)), f"Meals, next {plan.horizon_days} days"),
        ("potted_plant", "cream", str(plant_now), "Crops to plant"),
    ]
)

ui.heading("What spoils first", "See all" if len(risks) > 5 else None, "pantry")
if risks:
    ui.risk_rows(risks, items, limit=5)
else:
    ui.empty("The pantry is empty. Add food on the Pantry page.")

ui.heading("Cook this", "Recipes", "recipes", anchor="cook-this")
if plan.meals:
    ui.meal_rows(plan)
else:
    ui.empty(plan.summary)

ui.heading("Plant against the next gap", "Soil & farm", "farm")
if grow and snapshot:
    ui.balance(grow)
    st.write("")
    ui.crop_rows(grow)
else:
    st.warning(sensor_error or "No sensor reading.")
