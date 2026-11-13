"""Soil and farm: the sensor reading, soil, and what to plant."""

from __future__ import annotations

from datetime import date

import os

import streamlit as st
from pydantic import ValidationError

import fallow_ui as ui
from larder.achievements import ProgressStore, record_plant
from larder.grow.advisor import build_grow_plan
from larder.lifecycle import plant
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

ui.heading("Conditions", pill="Mock reading" if mode == "mock" else "Live", anchor="conditions")
ui.conditions(snapshot)

ui.heading("Pantry balance", "Food health", "health")
ui.balance(grow)

ui.heading("Plant")
if grow.crops:
    planted = set(ProgressStore().load().planted)

    def _plant(index: int) -> None:
        crop = grow.crops[index]
        amendment = next((i for i in items if i.state == "soil_amendment" and i.quantity > 0), None)
        store.save(plant(crop.crop, date.today(), amendment=amendment))  # growing; harvest it on Cycle
        st.session_state.fw_reward = record_plant(ProgressStore(), crop, grow.gaps)

    cols = st.columns(min(len(grow.crops), 3), gap="small")
    for index, crop in enumerate(grow.crops):
        with cols[index % len(cols)]:
            with st.container(key=f"card-crop-{index}"):
                ui.crop_rows(grow.model_copy(update={"crops": [crop]}))
                if crop.crop in planted:
                    st.html('<span class="fw-pill lime">Planted</span>')
                elif crop.action == "plant now":
                    st.button("Mark planted", key=f"plant-{index}", type="primary", icon=":material/potted_plant:",
                              on_click=_plant, args=(index,), width="stretch")
    ui.heading("Why these crops", anchor="why")
    ui.crop_reasons(grow)
else:
    ui.empty("Nothing to plant for this reading.")

if mode == "mock":
    st.caption("Mock mode replays fixtures/sensor.sample.json. Live mode is reserved for a real location, weather, and soil feed.")
with st.expander("Raw sensor reading"):
    st.json(snapshot.model_dump(mode="json"))
