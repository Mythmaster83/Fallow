"""Health: how well the pantry covers fresh food, calorie staples and protein."""

from __future__ import annotations

import streamlit as st

import fallow_ui as ui
from larder.achievements import ProgressStore, record_health_check
from larder.health.nutrition import nutrition_report
from larder.health.vitals import read_body_sample
from larder.llm.client import LLMClient
from larder.spoilage.predictor import predict_spoilage
from larder.store import open_store

store = open_store()
items = store.list_items()
risks = predict_spoilage(items, client=LLMClient.from_env())
report = nutrition_report(items, risks=risks)

checkup = record_health_check(ProgressStore())
if checkup is not None:
    st.session_state.fw_reward = checkup

ui.top("Health", f"{ui.today_label()} · food groups in reserve", avatar_icon="monitor_heart")

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

ui.heading("Body", pill="Sample reading")
try:
    body = read_body_sample()
except (OSError, ValueError):
    body = None
st.html(ui.health_card(body))

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
