"""Soil and farm: the sensor reading, soil, and what to plant."""

from __future__ import annotations

import os

import streamlit as st
from pydantic import ValidationError

import fallow_ui as ui
from larder.grow.advisor import build_grow_plan
from larder.llm.client import LLMClient
from larder.sensors import current_sensor
from larder.sensors.base import LiveSensorUnavailable
from larder.spoilage.predictor import predict_spoilage
from larder.store import open_store

mode = os.environ.get("SENSOR_MODE", "mock").strip().lower() or "mock"
store = open_store()
items = store.list_items()
risks = predict_spoilage(items, client=LLMClient.from_env())

ui.top("Soil & farm", f"{ui.today_label()} · sensor {mode}", avatar_icon="agriculture")

try:
    snapshot = current_sensor().read()
except (LiveSensorUnavailable, ValueError, ValidationError, FileNotFoundError, OSError) as exc:
    st.warning(str(exc))
    st.stop()

grow = build_grow_plan(snapshot, items, risks=risks)
plant_now = [c for c in grow.crops if c.action == "plant now"]
if plant_now:
    names = ", ".join(c.crop for c in plant_now)
    ui.feature("Plant now", f"{len(plant_now)} crops fit this weather", f"{names.capitalize()}.", "Why these", "#why", "potted_plant")
else:
    ui.feature("Hold off", "Nothing to plant yet", grow.balance_notes, "See conditions", "#conditions", "potted_plant")

SOURCE_PILL = {"live": "Live · Open-Meteo", "fallback": "Recorded (offline)", "mock": "Mock reading"}
ui.heading("Conditions", pill=SOURCE_PILL[snapshot.source], anchor="conditions")
if snapshot.note:
    st.caption(snapshot.note)
ui.conditions(snapshot)

ui.heading("Pantry balance", "Food health", "health")
ui.balance(grow)
if grow.soil_notes:
    st.caption(grow.soil_notes)

ui.heading("Plant")
if grow.crops:
    ui.crop_rows(grow)
    ui.heading("Why these crops", anchor="why")
    ui.crop_reasons(grow)
else:
    ui.empty("Nothing to plant for this reading.")

if snapshot.source == "mock":
    st.caption("Mock mode replays fixtures/sensor.sample.json. Set SENSOR_MODE=live for real weather and soil from Open-Meteo.")
elif snapshot.source == "live":
    st.caption(f"Live reading from Open-Meteo at {snapshot.captured_at:%H:%M}. Refreshes every 10 minutes.")
with st.expander("Raw sensor reading"):
    st.json(snapshot.model_dump(mode="json"))
