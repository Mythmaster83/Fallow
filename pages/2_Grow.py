"""Sensor reading, planting list, and pantry balance."""

from __future__ import annotations

import os

import streamlit as st

from larder.grow.advisor import build_grow_plan
from larder.llm.client import LLMClient, load_project_env
from larder.sensors import current_sensor
from larder.sensors.base import LiveSensorUnavailable
from larder.spoilage.predictor import predict_spoilage
from larder.store import open_store

load_project_env()
st.set_page_config(page_title="Grow · Fallow", page_icon="🌱", layout="wide")

st.title("Grow")
mode = os.environ.get("SENSOR_MODE", "mock").strip().lower() or "mock"
st.caption(
    f"Sensor mode is {mode}. Mock replays fixtures/sensor.sample.json. "
    "Live is reserved for a real location, weather, and soil feed."
)

store = open_store()
items = store.list_items()
risks = predict_spoilage(items, client=LLMClient.from_env())

try:
    snapshot = current_sensor().read()
except (LiveSensorUnavailable, ValueError, FileNotFoundError, OSError) as exc:
    st.warning(str(exc))
    st.stop()

grow = build_grow_plan(snapshot, items, risks=risks)

location, temperature, soil, frost = st.columns(4)
location.metric("Location", snapshot.location)
temperature.metric("Temperature", f"{snapshot.temp_c:.1f} °C")
moisture = "n/a" if snapshot.soil_moisture is None else f"{snapshot.soil_moisture:.0%} moisture"
soil.metric("Soil", snapshot.soil_condition, delta=moisture, delta_color="off")
frost.metric(
    "Frost",
    "yes" if snapshot.frost_risk else "no",
    delta=snapshot.weather,
    delta_color="off",
)

st.subheader("Balance")
st.write(grow.balance_notes)
if grow.gaps:
    st.caption("Thin reserves: " + ", ".join(grow.gaps))
else:
    st.caption("Fresh food, calorie staples, and protein all last past the next few days.")

if grow.soil_notes:
    st.subheader("Soil")
    st.write(grow.soil_notes)

st.subheader("Plant")
if grow.crops:
    st.dataframe(
        [
            {
                "crop": crop.crop,
                "action": crop.action,
                "fills": crop.fills,
                "why": crop.reason,
            }
            for crop in grow.crops
        ],
        width="stretch",
        hide_index=True,
    )
else:
    st.info("No crop fits this reading.")

with st.expander("Raw sensor reading"):
    st.json(snapshot.model_dump(mode="json"))
