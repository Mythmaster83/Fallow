"""Shared look for every Fallow page: one stylesheet plus small HTML blocks.

Style: soft lavender backdrop, an off-white app panel, white rounded cards,
pastel icon tiles, a dark feature card and lime accents. Built phone-first;
on a wide screen the panel sits centered on the lavender backdrop.

Every string that came from the inventory or the sensor is escaped before it
goes into HTML, so a food named ``<b>`` shows up as text.
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape

import streamlit as st

from larder.health.nutrition import NutritionReport
from larder.health.vitals import Vitals, stress_label
from larder.meals.recipes import Recipe
from larder.models import GrowPlan, InventoryItem, MealPlan, SpoilageRisk
from larder.sensors.base import SensorSnapshot, aqi_label

# Category -> (Material Symbols icon, pastel tile tone)
CATEGORY_ICON = {
    "leafy_greens": ("eco", "lime"),
    "produce": ("nutrition", "lime"),
    "berries": ("nutrition", "lav"),
    "dairy": ("water_full", "lav"),
    "meat": ("kebab_dining", "peach"),
    "fish": ("set_meal", "lav"),
    "eggs": ("egg", "cream"),
    "bread": ("bakery_dining", "cream"),
    "leftovers": ("takeout_dining", "peach"),
    "grain": ("rice_bowl", "cream"),
    "pantry": ("inventory_2", "cream"),
    "frozen": ("ac_unit", "lav"),
    "herb": ("spa", "lime"),
}
RISK_LABEL = {"critical": "Critical", "high": "High", "medium": "Medium", "low": "Low"}
RISK_TONE = {"critical": "red", "high": "peach", "medium": "cream", "low": "lime"}
RISK_COLOR = {"critical": "#F0604D", "high": "#F29B4B", "medium": "#E2B93B", "low": "#8DC63F"}
FILL_TONE = {"fresh food": "lime", "calorie staples": "cream", "protein": "lav"}
TILE_TONES = ["peach", "lime", "lav", "cream"]
GROUP_ICON = {"fresh food": ("eco", "lime"), "calorie staples": ("rice_bowl", "cream"), "protein": ("egg", "lav")}
STATUS_PILL = {"covered": ("lime", "Stocked"), "short": ("peach", "Running short"), "missing": ("red", "Missing")}
GROUP_IDEAS = {
    "fresh food": "Plant greens, or keep long-lasting produce like carrots, cabbage, apples and onions.",
    "calorie staples": "Keep dry rice, oats, pasta, flour or potatoes; they hold for months.",
    "protein": "Keep dried or canned beans, lentils, canned fish or peanut butter.",
}

CSS = """
<style>
:root{
  --lav-bg:#BBA6F0; --panel:#F6F5F2; --card:#FFFFFF; --ink:#1C1C28; --muted:#7D7C8C; --line:#ECEBF0;
  --dark:#1E1E2A; --lime:#D7F26E; --lime-ink:#3F5A00;
  --t-peach:#FCE6DA; --t-lime:#EEF8CF; --t-lav:#E6E2FB; --t-cream:#FFF0D6; --t-red:#FDE0DC;
}
[data-testid="stAppViewContainer"]{background:var(--lav-bg)}
[data-testid="stHeader"]{background:transparent}
[data-testid="stMainBlockContainer"]{background:var(--panel); border-radius:32px; max-width:1180px;
  margin:72px auto 32px; padding:28px 32px 40px !important; box-shadow:0 30px 60px -30px rgba(60,40,120,.35)}
@media (max-width:640px){
  [data-testid="stAppViewContainer"]{background:var(--panel)}
  [data-testid="stMainBlockContainer"]{border-radius:0; margin:48px 0 0; padding:16px 16px 40px !important; box-shadow:none}
}
.ms{font-family:'Material Symbols Rounded'; font-weight:400; font-style:normal; font-size:20px; line-height:1;
  letter-spacing:normal; text-transform:none; white-space:nowrap; direction:ltr; -webkit-font-smoothing:antialiased;
  font-feature-settings:'liga'; display:inline-block}
.fw-top{display:flex; align-items:center; justify-content:space-between; gap:12px}
.fw-hello{font-size:28px; font-weight:800; letter-spacing:-0.03em; margin:0; color:var(--ink); line-height:1.15}
.fw-sub{color:var(--muted); font-size:14px; margin-top:4px}
.fw-avatar{width:48px; height:48px; border-radius:50%; background:var(--lime); flex-shrink:0;
  display:flex; align-items:center; justify-content:center; color:var(--dark); box-shadow:0 0 0 3px #fff}
.fw-avatar .ms{font-size:24px}
.fw-search{display:flex; align-items:center; gap:10px; background:var(--card); border-radius:999px; height:48px;
  padding:0 18px; color:var(--muted); font-size:14px; text-decoration:none; margin-top:16px}
.fw-search:hover{color:var(--ink)}
.fw-h{display:flex; align-items:center; justify-content:space-between; margin:26px 0 12px}
.fw-h h3{font-size:20px; font-weight:700; margin:0; color:var(--ink); letter-spacing:-0.02em; padding:0}
.fw-h a{font-size:13px; color:var(--ink); font-weight:600}
.fw-pill{display:inline-flex; align-items:center; gap:4px; font-size:12px; font-weight:600; padding:6px 12px;
  border-radius:999px; white-space:nowrap}
.fw-pill.lime{background:var(--t-lime); color:var(--lime-ink)}
.fw-pill.lav{background:var(--t-lav); color:#3D358F}
.fw-pill.peach{background:var(--t-peach); color:#8A3B12}
.fw-pill.cream{background:var(--t-cream); color:#7A5200}
.fw-pill.red{background:var(--t-red); color:#A42A1A}
.fw-pill.ghost{background:var(--card); color:var(--ink); border:1px solid var(--line)}
.fw-tile{width:46px; height:46px; border-radius:14px; display:flex; align-items:center; justify-content:center;
  flex-shrink:0; color:var(--ink)}
.fw-tile.lime{background:var(--t-lime)} .fw-tile.lav{background:var(--t-lav)}
.fw-tile.peach{background:var(--t-peach)} .fw-tile.cream{background:var(--t-cream)} .fw-tile.red{background:var(--t-red)}
.fw-card{background:var(--card); border-radius:22px; padding:18px}
.fw-feature{background:var(--dark); color:#fff; border-radius:24px; padding:22px; position:relative; overflow:hidden;
  margin-top:18px}
.fw-feature .eyebrow{display:flex; align-items:center; gap:8px; font-size:13px; font-weight:600; color:#CFCDE0}
.fw-feature .title{font-size:24px; font-weight:700; letter-spacing:-0.02em; margin:14px 0 6px; max-width:70%; line-height:1.2}
.fw-feature .desc{font-size:13px; color:#B7B5C9; max-width:68%; line-height:1.5}
.fw-feature .cta{display:inline-flex; margin-top:16px; background:var(--lime); color:var(--dark); font-weight:700;
  font-size:13px; padding:10px 18px; border-radius:999px; text-decoration:none}
.fw-feature .blob{position:absolute; right:-28px; bottom:-28px; width:150px; height:150px; border-radius:50%;
  background:#2B2B3B; display:flex; align-items:center; justify-content:center}
.fw-feature .blob .ms{font-size:64px; color:var(--lime); margin:-18px 0 0 -18px}
.fw-stats{display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px}
.fw-stats.cols-3{grid-template-columns:repeat(3,minmax(0,1fr))}
@media (max-width:900px){.fw-stats,.fw-stats.cols-3{grid-template-columns:1fr}}
.fw-split{display:grid; grid-template-columns:1fr 1fr; background:var(--card); border-radius:22px; overflow:hidden}
.fw-half{padding:18px 18px 16px; min-width:0}
.fw-half + .fw-half{border-left:1px solid var(--line)}
@media (max-width:700px){
  .fw-split{grid-template-columns:1fr}
  .fw-half + .fw-half{border-left:0; border-top:1px solid var(--line)}
}
.fw-half-h{display:flex; align-items:center; gap:12px}
.fw-half-h .kicker{font-size:12px; color:var(--muted); font-weight:600}
.fw-half-h .place{font-size:16px; font-weight:700; color:var(--ink); margin-top:2px}
.fw-metrics{display:flex; gap:18px; margin-top:16px}
.fw-metrics b{display:block; font-size:22px; font-weight:800; letter-spacing:-0.02em; color:var(--ink)}
.fw-metrics span{display:block; font-size:12px; color:var(--muted); margin-top:2px}
.fw-warns{display:flex; flex-wrap:wrap; gap:6px; margin-top:14px}
.fw-vitals{display:grid; grid-template-columns:1fr 1fr; gap:12px 16px; margin-top:16px}
.fw-vital .l{font-size:12px; color:var(--muted); display:flex; align-items:center; gap:4px}
.fw-vital .l .ms{font-size:16px}
.fw-vital b{display:block; font-size:22px; font-weight:800; letter-spacing:-0.02em; color:var(--ink); margin-top:4px}
.fw-vital .u{font-size:12px; color:var(--muted); font-weight:600}
.fw-stat{background:var(--card); border-radius:22px; padding:16px; display:flex; flex-direction:column; gap:12px}
.fw-stat .row{display:flex; align-items:center; gap:10px}
.fw-stat .name{font-size:14px; font-weight:700; color:var(--ink); line-height:1.2}
.fw-stat .small{font-size:12px; color:var(--muted)}
.fw-stat .v{font-size:26px; font-weight:800; letter-spacing:-0.02em; color:var(--ink)}
.fw-chart .bars{display:flex; align-items:flex-end; justify-content:space-between; gap:10px; height:150px;
  margin-top:12px; padding:0 4px; background-image:linear-gradient(var(--line) 1px, transparent 1px);
  background-size:100% 37.5px}
.fw-chart .col{flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; position:relative}
.fw-chart .bar{width:10px; border-radius:6px; background:var(--dark)}
.fw-chart .bar.hot{background:var(--lime); width:12px}
.fw-chart .tip{position:absolute; top:-6px; background:var(--dark); color:#fff; font-size:11px; font-weight:600;
  padding:5px 8px; border-radius:8px; white-space:nowrap; left:-4px; transform:translateY(-100%); text-transform:capitalize}
.fw-chart .labels{display:flex; justify-content:space-between; gap:10px; padding:8px 4px 0}
.fw-chart .labels span{flex:1; text-align:center; font-size:11px; color:var(--muted); text-transform:capitalize;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.fw-chart .head{display:flex; justify-content:space-between; align-items:flex-start; gap:8px}
.fw-chart .title{font-size:18px; font-weight:700; color:var(--ink)}
.fw-chart .note{font-size:12px; color:var(--muted); margin-top:4px}
.fw-chart .note b{color:#5E7F00}
.fw-rows{display:flex; flex-direction:column; gap:10px}
.fw-row{background:var(--card); border-radius:20px; padding:14px; display:flex; align-items:center; gap:12px}
.fw-row .main{flex:1; min-width:0}
.fw-row .name{font-size:15px; font-weight:700; color:var(--ink); text-transform:capitalize;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.fw-row .small{font-size:12px; color:var(--muted); margin-top:3px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.fw-row .chev{width:30px; height:30px; border-radius:50%; background:var(--panel); display:flex;
  align-items:center; justify-content:center; flex-shrink:0; color:var(--ink)}
.fw-row .rem{text-align:left; flex-shrink:0; min-width:64px}
.fw-row .rem .small{margin-top:0}
.fw-row .rem b{font-size:14px; color:var(--ink)}
.fw-ring{display:flex; align-items:center; gap:8px; flex-shrink:0}
.fw-ring .r{width:26px; height:26px; border-radius:50%; display:flex; align-items:center; justify-content:center}
.fw-ring .r i{display:block; width:18px; height:18px; border-radius:50%; background:#fff}
.fw-ring b{font-size:13px; color:var(--ink); min-width:34px}
.fw-group{background:var(--card); border-radius:22px; padding:8px 14px}
.fw-group .fw-row{padding:12px 0; border-radius:0; border-bottom:1px solid var(--line)}
.fw-group .fw-row:last-child{border-bottom:0}
.fw-conds{display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px}
@media (max-width:900px){.fw-conds{grid-template-columns:repeat(2,minmax(0,1fr))}}
.fw-cond{background:var(--card); border-radius:20px; padding:14px}
.fw-cond .l{font-size:12px; color:var(--muted); display:flex; align-items:center; gap:6px}
.fw-cond .l .ms{font-size:16px}
.fw-cond .v{font-size:17px; font-weight:700; color:var(--ink); margin-top:8px; line-height:1.2}
.fw-cond .gauge{height:6px; background:var(--panel); border-radius:3px; margin-top:8px; overflow:hidden}
.fw-cond .gauge span{display:block; height:100%; background:var(--dark); border-radius:3px}
.fw-note{background:var(--t-lime); color:#2E4200; border-radius:20px; padding:14px 16px; font-size:14px;
  font-weight:600; display:flex; gap:10px; align-items:center; flex-wrap:wrap}
.fw-empty{background:var(--card); border-radius:20px; padding:18px; color:var(--muted); font-size:14px}
.fw-grid2{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px}
@media (max-width:900px){.fw-grid2{grid-template-columns:1fr}}
/* Streamlit widgets in the same style */
[class*="st-key-card-"], .st-key-addform{background:var(--card); border-radius:22px; padding:16px; gap:6px}
[class*="st-key-card-"] .fw-row{background:transparent}
.stButton button[kind="primary"]{background:var(--lime); color:var(--dark); border:0; font-weight:700; border-radius:999px; min-height:48px}
.stButton button[kind="primary"]:hover{background:#C9E85A; color:var(--dark)}
.stButton button[kind="tertiary"]{color:var(--muted)}
[data-testid="stTextInputRootElement"], [data-baseweb="select"] > div, [data-testid="stNumberInputContainer"],
[data-testid="stDateInputField"]{background:var(--panel) !important; border-radius:14px !important}
/* health + recipes */
.fw-groups{display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px}
@media (max-width:900px){.fw-groups{grid-template-columns:1fr}}
.fw-group-card{background:var(--card); border-radius:22px; padding:16px; display:flex; flex-direction:column; gap:10px}
.fw-group-card .top{display:flex; align-items:center; gap:10px}
.fw-group-card .name{font-size:15px; font-weight:700; color:var(--ink); flex:1}
.fw-group-card .lbl{font-size:12px; color:var(--muted)}
.fw-chips{display:flex; flex-wrap:wrap; gap:6px}
.fw-chip2{font-size:12px; padding:4px 10px; border-radius:999px; background:var(--panel); color:var(--ink)}
.fw-chip2.dim{color:var(--muted); text-decoration:line-through}
.fw-group-card .idea{font-size:13px; color:var(--muted); line-height:1.45; border-top:1px solid var(--line); padding-top:10px}
.fw-meter3{display:flex; gap:6px; margin-top:14px; max-width:58%; position:relative; z-index:1}
.fw-meter3 span{flex:1; height:8px; border-radius:4px; background:#3A3A4C}
.fw-meter3 span.on{background:var(--lime)}
.fw-recipe .head{display:flex; gap:12px; align-items:flex-start}
.fw-recipe .title{font-size:17px; font-weight:700; color:var(--ink); line-height:1.25}
.fw-recipe .meta{display:flex; flex-wrap:wrap; gap:6px; margin-top:6px}
.fw-recipe .why{font-size:13px; color:var(--muted); margin:10px 0}
.fw-recipe h4{font-size:13px; font-weight:700; color:var(--ink); margin:12px 0 8px; padding:0}
.fw-steps{margin:0 !important; padding:0 !important; list-style:none; counter-reset:s; display:flex; flex-direction:column; gap:8px}
.fw-steps li{margin:0 !important; padding:0 !important; counter-increment:s; display:flex; gap:10px; font-size:14px; line-height:1.45; color:var(--ink)}
.fw-steps li::before{content:counter(s); flex-shrink:0; width:24px; height:24px; border-radius:50%; background:var(--t-lime);
  color:var(--lime-ink); font-size:12px; font-weight:700; display:flex; align-items:center; justify-content:center}
</style>
"""


def inject_css() -> None:
    # The icon tiles use Material Symbols. Streamlit's own icons do not cover
    # these HTML blocks, so the face is loaded here.
    st.html(
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0">'
    )
    st.html(CSS)


def icon(name: str, size: int | None = None) -> str:
    style = f' style="font-size:{size}px"' if size else ""
    return f'<span class="ms" aria-hidden="true"{style}>{escape(name)}</span>'


def item_icon(category: str) -> tuple[str, str]:
    return CATEGORY_ICON.get(category, ("restaurant", "cream"))


def days_text(days: int) -> tuple[str, str]:
    """Number and label for a days-left count."""
    if days < 0:
        return str(-days), "days over"
    if days == 0:
        return "0", "today"
    return str(days), "day left" if days == 1 else "days left"


def days_short(days: int) -> str:
    if days < 0:
        return f"{-days}d over"
    if days == 0:
        return "Today"
    return f"{days} day" if days == 1 else f"{days} days"


def greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


def today_label() -> str:
    return date.today().strftime("%A, %b %d").replace(" 0", " ")


def top(title: str, subtitle: str, avatar_icon: str = "eco") -> None:
    st.html(
        f'<div class="fw-top"><div><p class="fw-hello">{escape(title)}</p>'
        f'<div class="fw-sub">{escape(subtitle)}</div></div>'
        f'<div class="fw-avatar">{icon(avatar_icon)}</div></div>'
    )


def search_link(label: str, href: str = "pantry") -> None:
    st.html(f'<a class="fw-search" href="{escape(href)}" target="_self">{icon("search")}{escape(label)}</a>')


def heading(
    title: str, link_label: str | None = None, href: str | None = None, pill: str | None = None, anchor: str | None = None
) -> None:
    right = ""
    if link_label and href:
        right = f'<a href="{escape(href)}" target="_self">{escape(link_label)}</a>'
    elif pill:
        right = f'<span class="fw-pill ghost">{escape(pill)}</span>'
    ident = f' id="{escape(anchor)}"' if anchor else ""
    st.html(f'<div class="fw-h"{ident}><h3>{escape(title)}</h3>{right}</div>')


def feature(eyebrow: str, title: str, desc: str, cta: str, href: str, glyph: str) -> None:
    st.html(
        f'<div class="fw-feature"><div class="eyebrow">{icon("bolt", 18)}{escape(eyebrow)}</div>'
        f'<div class="title">{escape(title)}</div><div class="desc">{escape(desc)}</div>'
        f'<a class="cta" href="{escape(href)}" target="_self">{escape(cta)}</a>'
        f'<div class="blob">{icon(glyph)}</div></div>'
    )


def stats(rows: list[tuple[str, str, str, str]]) -> None:
    """rows: (icon, tone, value, label)."""
    cells = "".join(
        f'<div class="fw-stat"><div class="row"><div class="fw-tile {escape(tone)}">{icon(ic)}</div>'
        f'<div class="name">{escape(label)}</div></div><div class="v">{escape(value)}</div></div>'
        for ic, tone, value, label in rows
    )
    cols = " cols-3" if len(rows) == 3 else ""
    st.html(f'<div class="fw-stats{cols}">{cells}</div>')


def _vital(glyph: str, label: str, value: str, unit: str) -> str:
    return (
        f'<div class="fw-vital"><div class="l">{icon(glyph)}{escape(label)}</div>'
        f'<b>{escape(value)} <span class="u">{escape(unit)}</span></b></div>'
    )


def condition_banner(snapshot: SensorSnapshot | None, vitals: Vitals | None, warnings: list[str]) -> None:
    """One card split in half: weather and warnings on the left, vitals on the right."""
    if snapshot is None:
        weather = '<div class="fw-metrics"><div><b>—</b><span>No weather reading</span></div></div>'
        place = "Weather"
    else:
        soil = snapshot.soil_condition.capitalize()
        weather = (
            '<div class="fw-metrics">'
            f'<div><b>{snapshot.temp_c:.0f}&deg;C</b><span>{escape(snapshot.weather)}</span></div>'
            f'<div><b>{escape(soil)}</b><span>Soil</span></div>'
            "</div>"
        )
        place = snapshot.location
    chips = "".join(f'<span class="fw-pill peach">{escape(note)}</span>' for note in warnings)
    warn_row = f'<div class="fw-warns">{chips}</div>' if chips else ""
    if vitals is None:
        body = '<div class="fw-metrics"><div><b>—</b><span>No wearable reading</span></div></div>'
    else:
        body = (
            '<div class="fw-vitals">'
            + _vital("favorite", "Heart rate", str(vitals.heart_rate_bpm), "bpm")
            + _vital("spo2", "Oxygen", str(vitals.spo2_percent), "%")
            + _vital("psychology", "Stress", stress_label(vitals.stress), str(vitals.stress))
            + _vital("air", "Respiration", str(vitals.respiration_per_min), "/min")
            + "</div>"
        )
    st.html(
        '<div class="fw-split">'
        f'<section class="fw-half"><div class="fw-half-h"><div class="fw-tile lav">{icon("cloud")}</div>'
        f'<div><div class="kicker">Weather</div><div class="place">{escape(place)}</div></div></div>'
        f"{weather}{warn_row}</section>"
        f'<section class="fw-half"><div class="fw-half-h"><div class="fw-tile peach">{icon("monitor_heart")}</div>'
        f'<div><div class="kicker">Vitals</div><div class="place">Wearable</div></div></div>'
        f"{body}</section></div>"
    )


def empty(text: str) -> None:
    st.html(f'<div class="fw-empty">{escape(text)}</div>')


def days_chart(risks: list[SpoilageRisk], limit: int = 7, cap: int = 7) -> None:
    """Bar chart of days left for the soonest items; the most urgent bar is lime."""
    shown = risks[:limit]
    if not shown:
        return
    cols, labels = [], []
    for i, risk in enumerate(shown):
        d = max(0, min(risk.days_remaining, cap))
        height = 14 + d / cap * 86
        hot = i == 0
        tip = f'<div class="tip">{escape(risk.item_name)} &middot; {escape(days_short(risk.days_remaining))}</div>' if hot else ""
        cols.append(
            f'<div class="col"><div class="bar{" hot" if hot else ""}" '
            f'style="height:{height:.0f}%;position:relative">{tip}</div></div>'
        )
        labels.append(f"<span>{escape(risk.item_name)}</span>")
    urgent = sum(1 for r in risks if r.days_remaining <= 2)
    st.html(
        '<div class="fw-card fw-chart"><div class="head"><div><div class="title">Days left</div>'
        f'<div class="note"><b>{urgent}</b> to cook within 2 days &middot; bars cap at {cap}</div></div>'
        f'<span class="fw-pill ghost">Soonest {len(shown)}</span></div>'
        f'<div class="bars" style="margin-top:44px">{"".join(cols)}</div>'
        f'<div class="labels">{"".join(labels)}</div></div>'
    )


def risk_rows(risks: list[SpoilageRisk], items: list[InventoryItem], limit: int | None = None) -> None:
    by_id = {i.id: i for i in items}
    rows = []
    for risk in risks[:limit] if limit else risks:
        item = by_id.get(risk.item_id)
        ic, tone = item_icon(item.category if item else "")
        where = f"{item.quantity:g} {item.unit} &middot; {escape(item.location)}" if item else ""
        rows.append(
            f'<div class="fw-row"><div class="fw-tile {tone}">{icon(ic)}</div>'
            f'<div class="main"><div class="name">{escape(risk.item_name)}</div><div class="small">{where}</div></div>'
            f'<div class="rem"><div class="small">Remaining</div><b>{escape(days_short(risk.days_remaining))}</b></div>'
            f'<span class="fw-pill {RISK_TONE[risk.risk]}">{RISK_LABEL[risk.risk]}</span></div>'
        )
    st.html(f'<div class="fw-rows">{"".join(rows)}</div>')


def meal_rows(plan: MealPlan) -> None:
    rows = []
    for i, meal in enumerate(plan.meals):
        tone = TILE_TONES[i % len(TILE_TONES)]
        uses = ", ".join(meal.uses)
        rows.append(
            f'<div class="fw-row"><div class="fw-tile {tone}">{icon("skillet")}</div>'
            f'<div class="main"><div class="name" style="text-transform:none;white-space:normal">{escape(meal.name)}</div>'
            f'<div class="small">Day {meal.day} &middot; {escape(uses)}</div></div>'
            f'<div class="chev">{icon("chevron_right", 18)}</div></div>'
        )
    st.html(f'<div class="fw-card fw-group">{"".join(rows)}</div>')


def conditions(snapshot: SensorSnapshot) -> None:
    moisture = snapshot.soil_moisture
    gauge = (
        f'<div class="gauge"><span style="width:{moisture * 100:.0f}%"></span></div>' if moisture is not None else ""
    )
    frost = '<span class="fw-pill red">Frost risk</span>' if snapshot.frost_risk else '<span class="fw-pill lime">No frost</span>'
    st.html(
        '<div class="fw-conds">'
        f'<div class="fw-cond"><div class="l">{icon("location_on")}Location</div><div class="v">{escape(snapshot.location)}</div></div>'
        f'<div class="fw-cond"><div class="l">{icon("thermostat")}Weather</div><div class="v">{snapshot.temp_c:.0f}&deg;C</div><div class="l" style="margin-top:4px">{escape(snapshot.weather)}</div></div>'
        f'<div class="fw-cond"><div class="l">{icon("water_drop")}Soil</div><div class="v">{escape(snapshot.soil_condition.capitalize())}</div>{gauge}</div>'
        f'<div class="fw-cond"><div class="l">{icon("ac_unit")}Frost</div><div class="v">{frost}</div></div>'
        "</div>"
    )


def environment_details(snapshot: SensorSnapshot) -> None:
    """Second row of condition cards: air, root-zone soil, humidity, wind and rain.

    A card appears only when the sensor actually read that value.
    """
    cards: list[str] = []
    air = snapshot.air
    if air is not None:
        tone = "lime" if air.us_aqi <= 50 else ("cream" if air.us_aqi <= 100 else "red")
        extra = []
        if air.pm2_5 is not None:
            extra.append(f"PM2.5 {air.pm2_5:.0f} µg/m³")
        if air.co2_ppm is not None:
            extra.append(f"CO₂ {air.co2_ppm:.0f} ppm")
        cards.append(
            f'<div class="fw-cond"><div class="l">{icon("air")}Air quality</div>'
            f'<div class="v">AQI {air.us_aqi} <span class="fw-pill {tone}">{escape(aqi_label(air.us_aqi))}</span></div>'
            f'<div class="l" style="margin-top:4px">{escape(" · ".join(extra))}</div></div>'
        )
    root = snapshot.soil_moisture_root
    if root is not None or snapshot.soil_temp_c is not None:
        value = f"{root * 100:.0f}% wet" if root is not None else "n/a"
        gauge = f'<div class="gauge"><span style="width:{root * 100:.0f}%"></span></div>' if root is not None else ""
        temp = f"{snapshot.soil_temp_c:.0f}&deg;C at 6 cm" if snapshot.soil_temp_c is not None else ""
        cards.append(
            f'<div class="fw-cond"><div class="l">{icon("grass")}Root zone (9–27 cm)</div>'
            f'<div class="v">{value}</div>{gauge}<div class="l" style="margin-top:4px">{temp}</div></div>'
        )
    if snapshot.humidity_pct is not None:
        cards.append(
            f'<div class="fw-cond"><div class="l">{icon("humidity_percentage")}Humidity</div>'
            f'<div class="v">{snapshot.humidity_pct:.0f}%</div></div>'
        )
    if snapshot.wind_kph is not None or snapshot.rain_today_mm is not None:
        wind = f"{snapshot.wind_kph:.0f} km/h" if snapshot.wind_kph is not None else "n/a"
        rain = f"{snapshot.rain_today_mm:.1f} mm rain today" if snapshot.rain_today_mm is not None else ""
        cards.append(
            f'<div class="fw-cond"><div class="l">{icon("wind_power")}Wind &amp; rain</div>'
            f'<div class="v">{wind}</div><div class="l" style="margin-top:4px">{rain}</div></div>'
        )
    if cards:
        st.html('<div class="fw-conds" style="margin-top:12px">' + "".join(cards) + "</div>")


def balance(grow: GrowPlan) -> None:
    gaps = "".join(f'<span class="fw-pill cream">{escape(g)}</span>' for g in grow.gaps)
    st.html(f'<div class="fw-note">{icon("balance")}<span style="flex:1 1 200px">{escape(grow.balance_notes)}</span>{gaps}</div>')


def crop_rows(grow: GrowPlan) -> None:
    rows = []
    for crop in grow.crops:
        tone = FILL_TONE.get(crop.fills, "lime")
        status = '<span class="fw-pill lime">Plant now</span>' if crop.action == "plant now" else '<span class="fw-pill peach">Wait</span>'
        rows.append(
            f'<div class="fw-row"><div class="fw-tile {tone}">{icon("potted_plant")}</div>'
            f'<div class="main"><div class="name">{escape(crop.crop)}</div>'
            f'<div class="small">Fills {escape(crop.fills)}</div></div>{status}</div>'
        )
    st.html(f'<div class="fw-rows">{"".join(rows)}</div>')


def crop_reasons(grow: GrowPlan) -> None:
    rows = "".join(
        f'<div class="fw-row"><div class="main"><div class="name">{escape(c.crop)}</div>'
        f'<div class="small" style="white-space:normal">{escape(c.reason)}</div></div></div>'
        for c in grow.crops
    )
    st.html(f'<div class="fw-card fw-group">{rows}</div>')


def source_note(risks: list[SpoilageRisk]) -> str:
    sources = {risk.source for risk in risks}
    if not sources or sources == {"heuristic"}:
        return "shelf-life table"
    if sources == {"llm"}:
        return "AI model"
    return "AI model + table"


def group_strip(report: NutritionReport) -> None:
    """Compact row of the three food groups with their status."""
    cells = []
    for g in report.groups:
        ic, tone = GROUP_ICON.get(g.group, ("restaurant", "cream"))
        ptone, plabel = STATUS_PILL[g.status]
        cells.append(
            f'<div class="fw-row"><div class="fw-tile {tone}">{icon(ic)}</div>'
            f'<div class="main"><div class="name">{escape(g.group)}</div>'
            f'<div class="small">{len(g.reserve)} in reserve &middot; {len(g.short)} short</div></div>'
            f'<span class="fw-pill {ptone}">{plabel}</span></div>'
        )
    st.html(f'<div class="fw-groups">{"".join(cells)}</div>')


def meter3(covered: int, total: int = 3) -> str:
    return '<div class="fw-meter3">' + "".join(
        f'<span class="{"on" if i < covered else ""}"></span>' for i in range(total)
    ) + "</div>"


def group_cards(report: NutritionReport) -> None:
    cards = []
    for g in report.groups:
        ic, tone = GROUP_ICON.get(g.group, ("restaurant", "cream"))
        ptone, plabel = STATUS_PILL[g.status]
        reserve = "".join(f'<span class="fw-chip2">{escape(n.capitalize())}</span>' for n in g.reserve) or '<span class="lbl">None</span>'
        short = "".join(f'<span class="fw-chip2 dim">{escape(n.capitalize())}</span>' for n in g.short) or '<span class="lbl">None</span>'
        idea = f'<div class="idea">{escape(GROUP_IDEAS.get(g.group, ""))}</div>' if g.status != "covered" else ""
        cards.append(
            f'<div class="fw-group-card"><div class="top"><div class="fw-tile {tone}">{icon(ic)}</div>'
            f'<div class="name">{escape(g.group.capitalize())}</div><span class="fw-pill {ptone}">{plabel}</span></div>'
            f'<div class="lbl">Lasts past 3 days</div><div class="fw-chips">{reserve}</div>'
            f'<div class="lbl">Spoils within 3 days</div><div class="fw-chips">{short}</div>{idea}</div>'
        )
    st.html(f'<div class="fw-groups">{"".join(cards)}</div>')


def recipe_card(recipe: Recipe, tone: str = "lime") -> None:
    ingredients = "".join(
        f'<span class="fw-chip2">{escape(i.name.capitalize())} &middot; {i.amount:g} {escape(i.unit)}</span>' for i in recipe.ingredients
    )
    steps = "".join(f"<li>{escape(step)}</li>" for step in recipe.steps)
    st.html(
        f'<div class="fw-recipe"><div class="head"><div class="fw-tile {tone}">{icon("skillet")}</div>'
        f'<div><div class="title">{escape(recipe.name)}</div><div class="meta">'
        f'<span class="fw-pill ghost">Day {recipe.day}</span>'
        f'<span class="fw-pill lav">{icon("schedule", 14)} about {recipe.minutes} min</span></div></div></div>'
        f'<div class="why">{escape(recipe.why[:1].upper() + recipe.why[1:])}</div>'
        f'<h4>From your pantry</h4><div class="fw-chips">{ingredients}</div>'
        f'<h4>Steps</h4><ol class="fw-steps">{steps}</ol></div>'
    )
