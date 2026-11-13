"""Health: how well the pantry covers fresh food, calorie staples and protein."""

from __future__ import annotations

from html import escape

import streamlit as st

import fallow_ui as ui
from larder.health.nutrition import nutrition_report
from larder.health.vitals import body_note, try_load_vitals
from larder.llm.client import LLMClient
from larder.sensors import current_sensor
from larder.sensors.base import LiveSensorUnavailable
from larder.sensors.warnings import condition_warnings
from larder.spoilage.predictor import predict_spoilage
from larder.store import open_store

store = open_store()
items = store.list_items()
risks = predict_spoilage(items, client=LLMClient.from_env())
report = nutrition_report(items, risks=risks)

ui.top("Health", f"{ui.today_label()} · body, supplies, and land", avatar_icon="monitor_heart")

# Body (wearable) and land (sensors): the two inputs beside the pantry.
vitals = try_load_vitals()
try:
    snapshot = current_sensor().read()
except (LiveSensorUnavailable, ValueError, FileNotFoundError, OSError):
    snapshot = None
ui.heading("Body and land")
ui.condition_banner(snapshot, vitals, condition_warnings(snapshot) if snapshot else ["No weather reading"])
st.html(f'<div class="fw-note">{ui.icon("tips_and_updates")}<span style="flex:1 1 200px">{escape(body_note(vitals))}</span></div>')
ui.heading("Supplies")

total = len(report.groups)
if not items:
    title, desc = "No food logged yet", "Add what you have on the Pantry page to see your balance."
elif report.covered == total:
    title, desc = "All food groups stocked", "Fresh food, calorie staples and protein all last past the next 3 days."
else:
    title = f"{report.covered} of {total} food groups stocked"
    desc = f"Running short on {', '.join(report.gaps)}. Food that spoils within 3 days does not count as a reserve."
st.html(
    f'<div class="fw-feature"><div class="eyebrow">{ui.icon("monitor_heart", 18)}Pantry balance</div>'
    f'<div class="title">{title}</div><div class="desc">{desc}</div>{ui.meter3(report.covered, total)}'
    f'<div class="blob">{ui.icon("nutrition")}</div></div>'
)

ui.heading("Food groups")
ui.group_cards(report)

if report.gaps:
    ui.heading("Close the gaps", "Soil & farm", "farm")
    st.html(
        '<div class="fw-note">'
        f'{ui.icon("tips_and_updates")}<span style="flex:1 1 200px">Use up the food that spoils soon first, '
        "then restock the groups marked short. The farm page shows which crops fill which gap.</span></div>"
    )

st.caption(
    "This is a pantry check, not medical advice. It counts which food groups you have on hand, "
    "not calories or nutrients."
)
