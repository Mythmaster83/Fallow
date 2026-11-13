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

ui.hero(
    "What the ground can give you next.",
    [("today", ui.today_label()), ("sensor", mode)],
)

try:
    snapshot = current_sensor().read()
except (LiveSensorUnavailable, ValueError, ValidationError, FileNotFoundError, OSError) as exc:
    st.warning(str(exc))
    st.stop()

grow = build_grow_plan(snapshot, items, risks=risks)

ui.section("Conditions")
ui.conditions(snapshot)
if mode == "mock":
    st.caption("Mock mode replays fixtures/sensor.sample.json. Live mode is reserved for a real location, weather, and soil feed.")

ui.section("Pantry balance")
ui.balance(grow)

ui.section("Plant")
if grow.crops:
    ui.crop_grid(grow)
else:
    ui.empty("Nothing to plant for this reading.")

with st.expander("Raw sensor reading"):
    st.json(snapshot.model_dump(mode="json"))
