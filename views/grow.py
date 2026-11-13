"""Grow: the sensor reading, the planting list, and pantry balance."""

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

ui.top("Grow", f"{ui.today_label()} · sensor {mode}", avatar_icon="potted_plant")

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

ui.heading("Conditions", pill="Mock reading" if mode == "mock" else "Live", anchor="conditions")
ui.conditions(snapshot)

ui.heading("Pantry balance")
ui.balance(grow)

ui.heading("Plant")
if grow.crops:
    ui.crop_rows(grow)
    ui.heading("Why these crops", anchor="why")
    ui.crop_reasons(grow)
else:
    ui.empty("Nothing to plant for this reading.")

if mode == "mock":
    st.caption("Mock mode replays fixtures/sensor.sample.json. Live mode is reserved for a real location, weather, and soil feed.")
with st.expander("Raw sensor reading"):
    st.json(snapshot.model_dump(mode="json"))
