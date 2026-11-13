"""Shared look for every Fallow page: one stylesheet plus small HTML blocks.

Pages pass in the same models the ``larder`` package returns. Every string
that came from the inventory or the sensor is escaped before it goes into
HTML, so a food named ``<b>`` shows up as text.
"""

from __future__ import annotations

from datetime import date
from html import escape

import streamlit as st

from larder.models import GrowPlan, MealPlan, SpoilageRisk
from larder.sensors.base import SensorSnapshot

RISK_LABEL = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}
FILL_TONE = {"fresh food": "green", "calorie staples": "yellow", "protein": "blue"}

CSS = """
<style>
:root{
  --bg:#0F1410; --panel:#161D17; --panel2:#1C251E; --line:#2A352C;
  --text:#E7EDE3; --muted:#9AA89C; --accent:#A6E35F;
  --critical:#FF6B5B; --high:#FFA24C; --medium:#F2D45C; --low:#6FCF97; --blue:#7FB6FF;
  --mono:'JetBrains Mono',ui-monospace,monospace; --head:'Space Grotesk',Inter,sans-serif;
}
[data-testid="stMainBlockContainer"]{padding-top:5rem !important; max-width:1240px}
h1,h2,h3{letter-spacing:-0.02em}
.fw-hero{display:flex; flex-wrap:wrap; gap:16px; align-items:flex-end; justify-content:space-between;
  padding:22px 24px; border:1px solid var(--line); border-radius:18px;
  background:linear-gradient(180deg,#18211A 0%,#131A14 100%); margin-bottom:6px}
.fw-brand{display:flex; gap:14px; align-items:center}
.fw-mark{width:46px; height:46px; border-radius:12px; background:var(--accent); display:flex;
  flex-direction:column; justify-content:center; gap:5px; padding:0 10px; box-sizing:border-box; flex-shrink:0}
.fw-mark span{display:block; height:4px; border-radius:2px; background:#0F1410}
.fw-mark span:nth-child(1){width:60%}
.fw-title{font-family:var(--head); font-size:34px; font-weight:700; line-height:1; margin:0; color:var(--text)}
.fw-tag{color:var(--muted); font-size:14px; margin-top:6px}
.fw-chips{display:flex; flex-wrap:wrap; gap:8px}
.fw-chip{font-family:var(--mono); font-size:12px; padding:5px 10px; border-radius:999px;
  border:1px solid var(--line); color:var(--muted); background:var(--panel)}
.fw-chip b{color:var(--text); font-weight:600}
.fw-chip.green{color:#0F1410; background:var(--low); border-color:var(--low)}
.fw-chip.yellow{color:#0F1410; background:var(--medium); border-color:var(--medium)}
.fw-chip.blue{color:#0F1410; background:var(--blue); border-color:var(--blue)}
.fw-chip.red{color:#0F1410; background:var(--critical); border-color:var(--critical)}
.fw-kpis{display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:10px 0 4px}
@media (max-width:900px){.fw-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
.fw-kpi{background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:14px 16px}
.fw-kpi .v{font-family:var(--head); font-size:32px; font-weight:700; line-height:1.1}
.fw-kpi .l{font-size:13px; color:var(--muted); margin-top:2px}
.fw-kpi.alert .v{color:var(--critical)}
.fw-kpi.good .v{color:var(--accent)}
.fw-sec{font-family:var(--mono); font-size:12px; letter-spacing:.12em; text-transform:uppercase;
  color:var(--muted); margin:18px 0 10px}
.fw-list{display:flex; flex-direction:column; gap:8px}
.fw-risk{display:grid; grid-template-columns:6px 1fr auto; gap:14px; align-items:center;
  background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:12px 16px 12px 0; overflow:hidden}
.fw-risk .bar{align-self:stretch; border-radius:0 4px 4px 0}
.fw-risk .name{font-weight:600; font-size:16px; text-transform:capitalize}
.fw-risk .why{font-size:13px; color:var(--muted); margin-top:2px}
.fw-risk .meter{height:4px; background:var(--line); border-radius:2px; margin-top:8px; overflow:hidden}
.fw-risk .meter span{display:block; height:100%; border-radius:2px}
.fw-risk .days{text-align:right}
.fw-risk .days .n{font-family:var(--head); font-size:22px; font-weight:700; line-height:1}
.fw-risk .days .t{font-family:var(--mono); font-size:11px; text-transform:uppercase; letter-spacing:.08em; margin-top:4px}
.fw-meal{background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:14px 16px;
  display:grid; grid-template-columns:52px 1fr; gap:14px}
.fw-day{font-family:var(--mono); text-align:center; border-radius:10px; background:var(--panel2);
  border:1px solid var(--line); padding:8px 0; height:fit-content}
.fw-day .d{font-size:10px; color:var(--muted); letter-spacing:.1em}
.fw-day .n{font-family:var(--head); font-size:22px; font-weight:700; color:var(--accent)}
.fw-meal .name{font-weight:600; font-size:16px}
.fw-meal .why{font-size:13px; color:var(--muted); margin:4px 0 8px}
.fw-uses{display:flex; flex-wrap:wrap; gap:6px}
.fw-use{font-size:12px; padding:3px 9px; border-radius:999px; background:var(--panel2);
  border:1px solid var(--line); text-transform:capitalize}
.fw-cond{display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px}
@media (max-width:900px){.fw-cond{grid-template-columns:repeat(2,minmax(0,1fr))}}
.fw-tile{background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:14px 16px}
.fw-tile .l{font-family:var(--mono); font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted)}
.fw-tile .v{font-family:var(--head); font-size:24px; font-weight:600; margin-top:6px; line-height:1.15}
.fw-tile .s{font-size:13px; color:var(--muted); margin-top:4px}
.fw-gauge{height:6px; background:var(--line); border-radius:3px; margin-top:10px; overflow:hidden}
.fw-gauge span{display:block; height:100%; background:var(--blue)}
.fw-crops{display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px}
@media (max-width:900px){.fw-crops{grid-template-columns:1fr}}
.fw-crop{background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:14px 16px;
  display:flex; flex-direction:column; gap:8px}
.fw-crop .top{display:flex; justify-content:space-between; align-items:center; gap:8px}
.fw-crop .name{font-family:var(--head); font-size:20px; font-weight:600; text-transform:capitalize}
.fw-crop .why{font-size:13px; color:var(--muted); line-height:1.45}
.fw-note{background:var(--panel); border:1px solid var(--line); border-left:0; border-radius:14px;
  padding:14px 16px; display:flex; gap:12px; align-items:center; flex-wrap:wrap}
.fw-note .txt{font-size:15px; flex:1 1 260px}
.fw-empty{background:var(--panel); border:1px dashed var(--line); border-radius:14px; padding:18px;
  color:var(--muted); font-size:14px}
.fw-item .name{font-weight:600; font-size:16px; text-transform:capitalize}
.fw-item .meta{font-size:13px; color:var(--muted); margin-top:2px}
.fw-item .row{display:flex; justify-content:space-between; align-items:center; gap:8px}
</style>
"""


def inject_css() -> None:
    st.html(CSS)


def days_text(days: int) -> tuple[str, str]:
    """Big number and its label for a days-left count."""
    if days < 0:
        return str(-days), "days over"
    if days == 0:
        return "0", "today"
    return str(days), "day left" if days == 1 else "days left"


def hero(subtitle: str, chips: list[tuple[str, str]]) -> None:
    chip_html = "".join(
        f'<span class="fw-chip">{escape(label)} <b>{escape(value)}</b></span>' for label, value in chips
    )
    st.html(
        f'<div class="fw-hero"><div class="fw-brand"><div class="fw-mark"><span></span><span></span><span></span></div>'
        f'<div><p class="fw-title">Fallow</p><div class="fw-tag">{escape(subtitle)}</div></div></div>'
        f'<div class="fw-chips">{chip_html}</div></div>'
    )


def section(label: str) -> None:
    st.html(f'<div class="fw-sec">{escape(label)}</div>')


def kpis(rows: list[tuple[str, str, str]]) -> None:
    """rows: (value, label, tone) where tone is '', 'alert' or 'good'."""
    cells = "".join(
        f'<div class="fw-kpi {escape(tone)}"><div class="v">{escape(value)}</div>'
        f'<div class="l">{escape(label)}</div></div>'
        for value, label, tone in rows
    )
    st.html(f'<div class="fw-kpis">{cells}</div>')


def empty(text: str) -> None:
    st.html(f'<div class="fw-empty">{escape(text)}</div>')


def risk_list(risks: list[SpoilageRisk], limit: int | None = None) -> None:
    shown = risks[:limit] if limit else risks
    rows = []
    for risk in shown:
        color = f"var(--{risk.risk})"
        n, label = days_text(risk.days_remaining)
        fresh = max(0, min(risk.days_remaining, 14)) / 14 * 100
        rows.append(
            f'<div class="fw-risk"><div class="bar" style="background:{color}"></div>'
            f'<div><div class="name">{escape(risk.item_name)}</div>'
            f'<div class="why">{escape(risk.reason)}</div>'
            f'<div class="meter"><span style="width:{fresh:.0f}%;background:{color}"></span></div></div>'
            f'<div class="days"><div class="n" style="color:{color}">{n}</div>'
            f'<div class="t" style="color:{color}">{label}</div></div></div>'
        )
    st.html(f'<div class="fw-list">{"".join(rows)}</div>')


def meal_list(plan: MealPlan) -> None:
    rows = []
    for meal in plan.meals:
        uses = "".join(f'<span class="fw-use">{escape(u)}</span>' for u in meal.uses)
        rows.append(
            f'<div class="fw-meal"><div class="fw-day"><div class="d">DAY</div>'
            f'<div class="n">{meal.day}</div></div>'
            f'<div><div class="name">{escape(meal.name)}</div>'
            f'<div class="why">{escape(meal.why)}</div><div class="fw-uses">{uses}</div></div></div>'
        )
    st.html(f'<div class="fw-list">{"".join(rows)}</div>')


def conditions(snapshot: SensorSnapshot) -> None:
    moisture = snapshot.soil_moisture
    gauge = (
        f'<div class="fw-gauge"><span style="width:{moisture * 100:.0f}%"></span></div>'
        if moisture is not None
        else ""
    )
    moist_text = f"{moisture * 100:.0f}% moisture" if moisture is not None else "moisture unknown"
    frost_tone = "red" if snapshot.frost_risk else "green"
    frost_text = "Frost risk" if snapshot.frost_risk else "No frost"
    st.html(
        '<div class="fw-cond">'
        f'<div class="fw-tile"><div class="l">Location</div><div class="v">{escape(snapshot.location)}</div>'
        f'<div class="s">Reading {escape(snapshot.captured_at.strftime("%b %d, %H:%M UTC"))}</div></div>'
        f'<div class="fw-tile"><div class="l">Weather</div><div class="v">{snapshot.temp_c:.0f}&deg;C</div>'
        f'<div class="s">{escape(snapshot.weather)}</div></div>'
        f'<div class="fw-tile"><div class="l">Soil</div><div class="v">{escape(snapshot.soil_condition)}</div>'
        f'<div class="s">{moist_text}</div>{gauge}</div>'
        f'<div class="fw-tile"><div class="l">Frost</div><div class="v" style="margin-top:10px">'
        f'<span class="fw-chip {frost_tone}">{frost_text}</span></div></div>'
        "</div>"
    )


def balance(grow: GrowPlan) -> None:
    gaps = "".join(f'<span class="fw-chip yellow">{escape(g)}</span>' for g in grow.gaps)
    label = '<span class="fw-chip">Thin reserves</span>' if grow.gaps else ""
    st.html(
        f'<div class="fw-note"><div class="txt">{escape(grow.balance_notes)}</div>'
        f'<div class="fw-chips">{label}{gaps}</div></div>'
    )


def crop_grid(grow: GrowPlan) -> None:
    cards = []
    for crop in grow.crops:
        tone = FILL_TONE.get(crop.fills, "green")
        action_tone = "green" if crop.action == "plant now" else ""
        cards.append(
            f'<div class="fw-crop"><div class="top"><span class="name">{escape(crop.crop)}</span>'
            f'<span class="fw-chip {action_tone}">{escape(crop.action)}</span></div>'
            f'<div class="why">{escape(crop.reason)}</div>'
            f'<div><span class="fw-chip {tone}">fills {escape(crop.fills)}</span></div></div>'
        )
    st.html(f'<div class="fw-crops">{"".join(cards)}</div>')


def source_note(risks: list[SpoilageRisk]) -> str:
    sources = {risk.source for risk in risks}
    if not sources or sources == {"heuristic"}:
        return "shelf-life table"
    if sources == {"llm"}:
        return "AI model"
    return "AI model + table"


def today_label() -> str:
    return date.today().strftime("%a %b %d").replace(" 0", " ")
