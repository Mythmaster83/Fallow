"""Fallow dashboard. Run with: streamlit run app.py"""

from __future__ import annotations

import os

import streamlit as st

from larder.grow.advisor import build_grow_plan
from larder.llm.client import LLMClient, load_project_env
from larder.meals.planner import plan_meals
from larder.models import SpoilageRisk
from larder.sensors import current_sensor
from larder.sensors.base import LiveSensorUnavailable
from larder.spoilage.predictor import predict_spoilage
from larder.store import open_store


def _source_caption(risks: list[SpoilageRisk]) -> str:
    sources = {risk.source for risk in risks}
    if sources == {"heuristic"}:
        return "These estimates come from the shelf-life table. Add LLM_API_KEY to ask a model instead."
    if sources == {"llm"}:
        return "These estimates come from the model."
    return "The model judged some items. The shelf-life table filled in the rest."


load_project_env()

st.set_page_config(page_title="Fallow", page_icon="🌿", layout="wide")

st.title("Fallow")
st.caption(
    "Nothing rots, nothing is wasted, everything is planned. "
    "The pantry, the next meals, and what to plant are on this page. "
    "Inventory and Grow are in the sidebar."
)

store = open_store()
items = store.list_items()
risks = predict_spoilage(items, client=LLMClient.from_env())
plan = plan_meals(items, risks=risks)

sensor_mode = os.environ.get("SENSOR_MODE", "mock").strip().lower() or "mock"
model_on = LLMClient.from_env() is not None
st.sidebar.caption(f"Sensor: {sensor_mode}")
st.sidebar.caption("Spoilage: model" if model_on else "Spoilage: shelf-life table")

left, right = st.columns(2)

with left:
    st.subheader("What spoils first")
    if not risks:
        st.info("The inventory is empty. Add food on the Inventory page.")
    else:
        st.dataframe(
            [
                {
                    "item": risk.item_name,
                    "risk": risk.risk,
                    "days left": risk.days_remaining,
                    "why": risk.reason,
                    "source": risk.source,
                }
                for risk in risks
            ],
            width="stretch",
            hide_index=True,
        )
        st.caption(_source_caption(risks))

with right:
    st.subheader("Cook this")
    st.write(plan.summary)
    if plan.meals:
        st.dataframe(
            [
                {
                    "day": meal.day,
                    "meal": meal.name,
                    "uses": ", ".join(meal.uses),
                    "why": meal.why,
                }
                for meal in plan.meals
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No meal is queued. Either the kitchen is empty or nothing is close to spoiling.")

st.subheader("Plant against the next gap")
try:
    snapshot = current_sensor().read()
except (LiveSensorUnavailable, ValueError, FileNotFoundError, OSError) as exc:
    st.warning(str(exc))
else:
    grow = build_grow_plan(snapshot, items, risks=risks)
    place, weather, soil = st.columns(3)
    place.metric("Location", snapshot.location)
    weather.metric("Weather", f"{snapshot.temp_c:.0f} °C", delta=snapshot.weather, delta_color="off")
    soil.metric(
        "Soil",
        snapshot.soil_condition,
        delta="frost risk" if snapshot.frost_risk else "no frost",
        delta_color="off",
    )
    st.write(grow.balance_notes)
    if grow.gaps:
        st.caption("Thin reserves: " + ", ".join(grow.gaps))
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
