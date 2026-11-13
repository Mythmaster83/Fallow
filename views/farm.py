"""Soil and farm: the sensor reading, soil, and what to plant."""

from __future__ import annotations

import os
from datetime import date

import streamlit as st
from pydantic import ValidationError

import fallow_ui as ui
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

SOURCE_PILL = {"live": "Live · Open-Meteo", "fallback": "Recorded (offline)", "mock": "Mock reading"}
ui.heading("Conditions", pill=SOURCE_PILL[snapshot.source], anchor="conditions")
if snapshot.note:
    st.caption(snapshot.note)
ui.conditions(snapshot)

ui.heading("Pantry balance", "Food health", "health")
ui.balance(grow)
if grow.soil_notes:
    st.caption(grow.soil_notes)

flash = st.session_state.pop("farm_flash", None)
if flash:
    st.success(flash, icon=":material/check_circle:")


def _plant(crop: str) -> None:
    """Put the crop in the ground, digging in finished compost if there is some."""
    amendment = next((i for i in items if i.state == "soil_amendment" and i.quantity > 0), None)
    store.save(plant(crop, date.today(), amendment=amendment))
    fed = f", fed with {amendment.name}" if amendment else ""
    st.session_state.farm_flash = f"Planted {crop}{fed}. It's growing on the Cycle page; harvest it there."


growing = {i.name.lower() for i in items if i.state == "growing"}
ui.heading("Plant")
if grow.crops:
    ui.crop_rows(grow)
    sow = [c for c in grow.crops if c.action == "plant now"]
    if sow:
        cols = st.columns(len(sow))
        for col, crop in zip(cols, sow):
            in_ground = crop.crop.lower() in growing
            col.button(
                f"{crop.crop.capitalize()} is in" if in_ground else f"Plant {crop.crop}",
                key=f"plant-{crop.crop}",
                icon=":material/check:" if in_ground else ":material/potted_plant:",
                type="secondary" if in_ground else "primary",
                disabled=in_ground,
                on_click=_plant,
                args=(crop.crop,),
                width="stretch",
            )
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
