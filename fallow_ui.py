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

from larder.achievements import CATALOG, XP_PER_LEVEL, Progress, Reward
from larder.health.nutrition import NutritionReport
from larder.health.body import BodySnapshot, co2_label, heart_rate_label, radiation_label, spo2_label
from larder.meals.recipes import Recipe
from larder.models import GrowPlan, InventoryItem, MealPlan, SpoilageRisk
from larder.sensors.base import SensorSnapshot

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
/* Fallow design system.
   Color has jobs: charcoal ink for text and the current page, lime for the one
   action that matters, red / amber / green only for status, lavender as a quiet
   brand accent. Everything else is neutral. One radius scale (12 / 8 / 6),
   1px borders instead of shadows, Plus Jakarta for words, tabular figures for
   numbers. Motion only where it carries meaning (achievements). */
:root{
  --bg:#F5F4F0; --panel:#F5F4F0; --card:#FFFFFF; --sunk:#F3F2EE;
  --ink:#17171F; --ink-2:#3E3D4A; --muted:#74737F; --faint:#A6A5B0;
  --line:#E7E5EC; --line-2:#F0EFF3;
  --dark:#1C1C26; --dark-2:#2A2A36;
  --lime:#D4EF6A; --lime-hover:#C8E658; --lime-ink:#3F5A00;
  --lav:#8E7BE0; --lav-soft:#F0ECFD; --lav-ink:#5B46C7; --lav-bar:#A897EC;
  --sh-1:0 1px 2px rgba(23,23,31,.04), 0 8px 24px -12px rgba(48,36,110,.14);
  --sh-2:0 2px 4px rgba(23,23,31,.05), 0 18px 40px -18px rgba(48,36,110,.28);
  --ok:#4E7A00; --ok-bg:#EDF5DA; --warn:#9A6200; --warn-bg:#FBF0D9;
  --hot:#B3470F; --hot-bg:#FCEBE1; --bad:#B4331F; --bad-bg:#FBE6E2;
  --t-peach:var(--hot-bg); --t-lime:var(--ok-bg); --t-lav:var(--lav-soft); --t-cream:var(--warn-bg); --t-red:var(--bad-bg);
  --r-lg:18px; --r:12px; --r-sm:999px;
}

/* ---- Page frame: full bleed, content column ---- */
[data-testid="stAppViewContainer"]{background:radial-gradient(1200px 420px at 50% -120px, #C9BBF6 0%, #E4DCFB 45%, rgba(245,244,240,0) 100%), var(--bg); background-repeat:no-repeat}
[data-testid="stHeader"]{display:none}
[data-testid="stMainBlockContainer"]{max-width:1160px; margin:0 auto; padding:92px 32px 64px !important}
.ms{font-family:'Material Symbols Rounded'; font-weight:400; font-style:normal; font-size:20px; line-height:1;
  letter-spacing:normal; text-transform:none; white-space:nowrap; direction:ltr; -webkit-font-smoothing:antialiased;
  font-feature-settings:'liga'; display:inline-block}

/* ---- Page header ---- */
.fw-top{display:flex; align-items:flex-end; justify-content:space-between; gap:16px; padding-bottom:4px}
.fw-lhs{display:flex; align-items:center; gap:12px; min-width:0}
.fw-avatar{display:none}
.fw-hello{font-size:32px; font-weight:800; letter-spacing:-0.035em; margin:0; color:var(--ink); line-height:1.2}
.fw-sub{color:var(--ink-2); opacity:.75; font-size:14.5px; margin-top:6px}
.fw-topbtns{display:flex; align-items:center; gap:8px; flex-shrink:0}
.fw-sbtn{width:40px; height:40px; border-radius:var(--r); background:var(--card); border:1px solid var(--line); color:var(--ink-2);
  display:flex; align-items:center; justify-content:center; text-decoration:none}
.fw-sbtn:hover{border-color:var(--ink-2); color:var(--ink)}
.fw-sbtn .ms{font-size:20px}
.fw-search{display:flex; align-items:center; gap:10px; background:var(--card); border:1px solid var(--line); border-radius:var(--r);
  height:42px; padding:0 14px; color:var(--muted); font-size:14px; text-decoration:none; margin-top:16px}
.fw-search:hover{color:var(--ink); border-color:var(--ink-2)}

/* ---- Section headings ---- */
.fw-h{display:flex; align-items:baseline; justify-content:space-between; gap:12px; margin:32px 0 12px}
.fw-h h3{font-size:19px; font-weight:800; margin:0; padding:0; color:var(--ink); letter-spacing:-0.01em}
.fw-h a{font-size:13.5px; font-weight:600; color:var(--lav-ink); text-decoration:none; white-space:nowrap}
.fw-h a:hover{color:var(--ink); text-decoration:underline; text-underline-offset:3px}

/* ---- Status labels ---- */
.fw-pill{display:inline-flex; align-items:center; gap:4px; font-size:12px; font-weight:700; padding:4px 10px;
  border-radius:var(--r-sm); white-space:nowrap; line-height:1.45}
.fw-pill .ms{font-size:14px}
.fw-pill.lime{background:var(--ok-bg); color:var(--ok)}
.fw-pill.cream{background:var(--warn-bg); color:var(--warn)}
.fw-pill.peach{background:var(--hot-bg); color:var(--hot)}
.fw-pill.red{background:var(--bad-bg); color:var(--bad)}
.fw-pill.lav{background:var(--lav-soft); color:#4A3D99}
.fw-pill.ghost{background:transparent; color:var(--ink-2); box-shadow:inset 0 0 0 1px var(--line)}

/* ---- Icon tiles: neutral; status lives in labels, not tile colors ---- */
.fw-tile{width:40px; height:40px; border-radius:12px; display:flex; align-items:center; justify-content:center;
  flex-shrink:0; background:var(--lav-soft); color:var(--lav-ink)}
.fw-tile .ms{font-size:21px}
.fw-tile.lime, .fw-tile.lav, .fw-tile.peach, .fw-tile.cream, .fw-tile.red{background:var(--lav-soft)}

/* ---- Surfaces ---- */
.fw-card, .fw-stat, .fw-cond, .fw-group, .fw-group-card, .fw-empty, .fw-rows,
[class*="st-key-card-"], .st-key-addform{background:var(--card); border:1px solid rgba(23,23,31,.05); border-radius:var(--r-lg); box-shadow:var(--sh-1)}
.fw-card{padding:20px}
.fw-empty{padding:18px; color:var(--muted); font-size:14px}
.fw-card .chead{display:flex; justify-content:space-between; align-items:center; gap:8px}
.fw-card .ctitle{font-size:16px; font-weight:800; color:var(--ink); display:flex; align-items:center; gap:8px}
.fw-card .ctitle .ms{font-size:20px; color:var(--lav-ink)}
.fw-foot{font-size:12px; color:var(--muted); margin-top:12px}

/* ---- Next-action banner ---- */
.fw-feature{background:radial-gradient(420px 220px at 100% 0%, rgba(212,239,106,.20), transparent 70%), radial-gradient(520px 260px at 0% 120%, rgba(142,123,224,.35), transparent 70%), var(--dark); color:#fff; border-radius:var(--r-lg); padding:26px 28px; box-shadow:var(--sh-2); position:relative; overflow:hidden; margin-top:20px}
.fw-feature .eyebrow{display:flex; align-items:center; gap:6px; font-size:13px; font-weight:600; color:#B9B7CC}
.fw-feature .eyebrow .ms{font-size:16px; color:var(--lime)}
.fw-feature .title{font-size:26px; font-weight:800; letter-spacing:-0.02em; margin:8px 0 4px; line-height:1.25}
.fw-feature .desc{font-size:14px; color:#B9B7CC; line-height:1.5; max-width:62ch}
.fw-feature .cta{display:inline-flex; align-items:center; margin-top:18px; background:var(--lime); color:var(--ink); font-weight:700;
  font-size:14px; padding:10px 18px; border-radius:var(--r-sm); text-decoration:none}
.fw-feature .cta:hover{background:var(--lime-hover)}
.fw-feature .blob{position:absolute; right:28px; top:50%; transform:translateY(-50%); width:84px; height:84px; border-radius:22px;
  background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.10); display:flex; align-items:center; justify-content:center}
.fw-feature .blob .ms{font-size:40px; color:var(--lime)}
.fw-feature .title, .fw-feature .desc{max-width:calc(100% - 120px)}
@media (max-width:640px){.fw-feature .blob{display:none} .fw-feature .title, .fw-feature .desc{max-width:100%}}
.fw-meter3{display:flex; gap:4px; margin-top:14px; max-width:240px}
.fw-meter3 span{flex:1; height:6px; border-radius:3px; background:#3A3A48}
.fw-meter3 span.on{background:var(--lime)}
.fw-meter3.light span{background:var(--line-2)}
.fw-meter3.light span.on{background:var(--ok)}

/* ---- Stat tiles ---- */
.fw-stats{display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px}
@media (max-width:900px){.fw-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
.fw-stat{padding:18px; display:flex; flex-direction:column; gap:14px}
.fw-stat .row{display:flex; align-items:center; gap:10px}
.fw-stat .name{font-size:13px; font-weight:600; color:var(--muted); line-height:1.3}
.fw-stat .small{font-size:12px; color:var(--muted)}
.fw-stat .v{font-size:34px; font-weight:800; letter-spacing:-0.03em; color:var(--ink); font-variant-numeric:tabular-nums}

/* ---- Spoilage chart ---- */
.fw-chart .head{display:flex; justify-content:space-between; align-items:flex-start; gap:8px}
.fw-chart .title{font-size:16px; font-weight:800; color:var(--ink)}
.fw-chart .note{font-size:12.5px; color:var(--muted); margin-top:3px}
.fw-chart .note b{color:var(--bad)}
.fw-chart .bars{display:flex; align-items:flex-end; justify-content:space-between; gap:10px; height:150px; margin-top:12px;
  padding:0 4px; border-bottom:1px solid var(--line);
  background-image:linear-gradient(var(--line-2) 1px, transparent 1px); background-size:100% 37.5px}
.fw-chart .col{flex:1; display:flex; flex-direction:column; align-items:center; justify-content:flex-end; height:100%; position:relative}
.fw-chart .bar{width:18px; border-radius:6px 6px 2px 2px; background:var(--lav-bar)}
.fw-chart .bar.hot{background:#E2553F; width:18px}
.fw-chart .tip{position:absolute; top:-6px; left:50%; transform:translate(-50%,-100%); background:var(--dark); color:#fff;
  font-size:11px; font-weight:600; padding:4px 7px; border-radius:var(--r-sm); white-space:nowrap; text-transform:capitalize}
.fw-chart .labels{display:flex; justify-content:space-between; gap:10px; padding:8px 4px 0}
.fw-chart .labels span{flex:1; text-align:center; font-size:11.5px; color:var(--muted); text-transform:capitalize;
  overflow:hidden; text-overflow:ellipsis; white-space:nowrap}

/* ---- Rows: always one table, divided by hairlines ---- */
.fw-rows{display:flex; flex-direction:column; overflow:hidden}
.fw-row{display:flex; align-items:center; gap:14px; padding:14px 18px; background:transparent; border-bottom:1px solid var(--line-2)}
.fw-rows > .fw-row:last-child, .fw-group > .fw-row:last-child{border-bottom:0}
.fw-row .main{flex:1; min-width:0}
.fw-row .name{font-size:14.5px; font-weight:700; color:var(--ink); text-transform:capitalize; overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.fw-row .small{font-size:12.5px; color:var(--muted); margin-top:2px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.fw-row .chev{flex-shrink:0; color:var(--faint); display:flex}
.fw-row .rem{flex-shrink:0; min-width:60px; text-align:right}
.fw-row .rem .small{display:none}
.fw-row .rem b{font-size:13px; font-weight:600; color:var(--ink-2); font-variant-numeric:tabular-nums}
.fw-group{padding:0 18px}
.fw-group .fw-row{padding:12px 0}
[class*="st-key-card-"]{padding:14px 16px; gap:4px}
[class*="st-key-card-"] .fw-row{background:transparent; padding:0 !important; border:0}
[class*="st-key-card-"] .fw-rows{border:0; background:transparent; border-radius:0}
/* Repeated per-card actions are quiet; lime stays for the page's main action. */
[class*="st-key-card-crop"] .stButton button[kind="primary"], [class*="st-key-card-recipe"] .stButton button[kind="primary"]{
  background:var(--card); color:var(--ink); box-shadow:inset 0 0 0 1px var(--line); min-height:38px}
[class*="st-key-card-crop"] .stButton button[kind="primary"]:hover, [class*="st-key-card-recipe"] .stButton button[kind="primary"]:hover{
  background:var(--dark); color:#fff; box-shadow:none}
.fw-ring{display:flex; align-items:center; gap:8px; flex-shrink:0}
.fw-ring .r{width:24px; height:24px; border-radius:50%; display:flex; align-items:center; justify-content:center}
.fw-ring .r i{display:block; width:16px; height:16px; border-radius:50%; background:#fff}
.fw-ring b{font-size:13px; color:var(--ink); min-width:34px; font-variant-numeric:tabular-nums}

/* ---- Conditions (farm) ---- */
.fw-conds{display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px}
@media (max-width:900px){.fw-conds{grid-template-columns:repeat(2,minmax(0,1fr))}}
.fw-cond{padding:14px 16px}
.fw-cond .l{font-size:12.5px; color:var(--muted); display:flex; align-items:center; gap:6px}
.fw-cond .l .ms{font-size:16px}
.fw-cond .v{font-size:16px; font-weight:700; color:var(--ink); margin-top:6px; line-height:1.3}
.fw-cond .gauge{height:4px; background:var(--line-2); border-radius:2px; margin-top:8px; overflow:hidden}
.fw-cond .gauge span{display:block; height:100%; background:var(--ink-2); border-radius:2px}

/* ---- Notes, chips, groups ---- */
.fw-note{background:var(--ok-bg); color:#2D4400; border-radius:var(--r-lg); padding:12px 16px; font-size:14px;
  font-weight:500; display:flex; gap:10px; align-items:center; flex-wrap:wrap}
.fw-note .ms{font-size:18px}
.fw-grid2{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px}
@media (max-width:900px){.fw-grid2{grid-template-columns:1fr}}
.fw-groups{display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px}
@media (max-width:900px){.fw-groups{grid-template-columns:1fr}}
.fw-groups > .fw-row{background:var(--card); border:1px solid var(--line); border-radius:var(--r-lg)}
.fw-group-card{padding:16px; display:flex; flex-direction:column; gap:10px}
.fw-group-card .top{display:flex; align-items:center; gap:10px}
.fw-group-card .name{font-size:15px; font-weight:700; color:var(--ink); flex:1}
.fw-group-card .lbl{font-size:12.5px; color:var(--muted)}
.fw-group-card .idea{font-size:13px; color:var(--muted); line-height:1.5; border-top:1px solid var(--line-2); padding-top:10px}
.fw-chips{display:flex; flex-wrap:wrap; gap:6px}
.fw-chip2{font-size:12.5px; padding:3px 9px; border-radius:var(--r-sm); background:var(--sunk); color:var(--ink-2)}
.fw-chip2.dim{color:var(--faint); text-decoration:line-through}

/* ---- Recipes ---- */
.fw-recipe .head{display:flex; gap:12px; align-items:flex-start}
.fw-recipe .title{font-size:16px; font-weight:700; color:var(--ink); line-height:1.3}
.fw-recipe .meta{display:flex; flex-wrap:wrap; gap:6px; margin-top:6px}
.fw-recipe .why{font-size:13.5px; color:var(--muted); margin:10px 0; line-height:1.5}
.fw-recipe h4{font-size:13px; font-weight:700; color:var(--ink); margin:14px 0 8px; padding:0}
.fw-steps{margin:0 !important; padding:0 !important; list-style:none; counter-reset:s; display:flex; flex-direction:column; gap:8px}
.fw-steps li{margin:0 !important; padding:0 !important; counter-increment:s; display:flex; gap:10px; font-size:14px; line-height:1.5; color:var(--ink)}
.fw-steps li::before{content:counter(s); flex-shrink:0; width:24px; height:24px; border-radius:50%; background:var(--lav-soft);
  color:var(--lav-ink); font-size:12px; font-weight:700; display:flex; align-items:center; justify-content:center; font-variant-numeric:tabular-nums}

/* ---- Weather + Health cards ---- */
.fw-duo{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin-top:12px; align-items:stretch}
.fw-duo > .fw-card{display:flex; flex-direction:column}
.fw-duo > .fw-card .fw-foot{margin-top:auto; padding-top:12px}
.fw-wx .now{display:flex; align-items:center; gap:14px; margin:14px 0 4px}
.fw-wx .deg{font-size:48px; font-weight:800; letter-spacing:-0.04em; color:var(--ink); line-height:1; font-variant-numeric:tabular-nums}
.fw-wx .cond{font-size:15px; font-weight:700; color:var(--ink)}
.fw-mini{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin-top:14px}
.fw-mini .m{background:#F7F5FE; border-radius:14px; padding:14px}
.fw-mini .k{font-size:12.5px; color:var(--muted); display:flex; align-items:center; gap:6px}
.fw-mini .k .ms{font-size:16px}
.fw-mini .v{font-size:18px; font-weight:700; color:var(--ink); margin:6px 0; letter-spacing:-0.02em; font-variant-numeric:tabular-nums}
.fw-mini .v small, .fw-mini .pair small{font-size:12px; font-weight:500; color:var(--muted); margin-left:3px}
.fw-mini .pair{display:flex; align-items:baseline; gap:5px; margin:6px 0; font-size:15px; color:var(--ink)}
.fw-mini .pair .ms{align-self:center; color:var(--faint); font-size:16px}
.fw-mini .pair b{font-weight:700; font-variant-numeric:tabular-nums}
@media (max-width:640px){
  .fw-duo{grid-template-columns:1fr}
  .fw-duo .fw-mini{gap:8px}
}

/* ---- Your cycle: stepper, badges, XP ---- */
.fw-cycle{display:flex; align-items:flex-start; justify-content:space-between; position:relative; margin:18px 4px 6px}
.fw-cycle .line{position:absolute; top:21px; left:12%; right:12%; height:2px; background:var(--line)}
.fw-cycle .line span{display:block; height:100%; background:var(--lav)}
.fw-step{position:relative; z-index:1; flex:1; display:flex; flex-direction:column; align-items:center; gap:8px; text-decoration:none; color:var(--ink)}
.fw-step .dot{width:44px; height:44px; border-radius:50%; background:var(--card); border:1px solid var(--line); color:var(--muted);
  display:flex; align-items:center; justify-content:center; position:relative}
.fw-step.done .dot{background:var(--lime); border-color:transparent; color:var(--ink)}
.fw-step.next .dot{background:var(--dark); border-color:var(--dark); color:var(--lime)}
.fw-step .chk{position:absolute; right:-3px; bottom:-3px; width:18px; height:18px; border-radius:50%; background:var(--ok); color:#fff;
  display:flex; align-items:center; justify-content:center; box-shadow:0 0 0 2px var(--card)}
.fw-step .chk .ms{font-size:13px}
.fw-step .lbl{font-size:12.5px; font-weight:600; text-align:center; line-height:1.3}
.fw-badges{display:flex; flex-wrap:wrap; gap:8px; margin-top:14px}
.fw-badge{width:40px; height:40px; border-radius:var(--r); display:flex; align-items:center; justify-content:center;
  background:var(--sunk); color:var(--faint)}
.fw-badge .ms{font-size:19px}
.fw-badge.on{background:var(--lav-soft); color:var(--lav-ink)}
.fw-xp{display:flex; justify-content:space-between; font-size:12.5px; color:var(--muted); margin-top:14px}
.fw-xp b{color:var(--ink)}
.fw-xpbar{height:6px; border-radius:3px; background:var(--line-2); overflow:hidden; margin-top:6px}
.fw-xpbar span{display:block; height:100%; border-radius:3px; background:linear-gradient(90deg, var(--lav), var(--lav-ink))}

/* ---- Achievement popup: the one place with motion ---- */
.fw-ach-wrap{position:fixed; inset:0; z-index:999999; display:flex; align-items:flex-start; justify-content:center;
  padding-top:96px; pointer-events:none; animation:fw-ach-out .35s ease-in 5s forwards}
.fw-ach-wrap:has(input:checked){display:none}
.fw-ach{pointer-events:auto; position:relative; width:min(340px,88vw); background:var(--dark); color:#fff; border-radius:16px;
  padding:24px 22px 20px; text-align:center; box-shadow:0 24px 60px -24px rgba(20,20,30,.6)}
.fw-ach .x{position:absolute; top:10px; right:10px; width:32px; height:32px; border-radius:var(--r); display:flex;
  align-items:center; justify-content:center; color:#B9B7CC; cursor:pointer}
.fw-ach .x input{position:absolute; opacity:0; width:0; height:0}
.fw-ach-badge{width:64px; height:64px; margin:0 auto 12px; border-radius:16px; background:var(--lime); color:var(--ink);
  display:flex; align-items:center; justify-content:center; position:relative; overflow:hidden}
.fw-ach-badge .ms{font-size:34px}
.fw-ach-badge .shine{display:none}
.fw-ach .eyebrow{font-size:12px; font-weight:700; color:var(--lime)}
.fw-ach .title{font-size:20px; font-weight:700; letter-spacing:-0.02em; margin:4px 0}
.fw-ach .desc{font-size:13.5px; color:#B9B7CC; line-height:1.5}
.fw-ach .more{display:flex; flex-wrap:wrap; justify-content:center; gap:6px; margin-top:10px}
.fw-ach .more span{font-size:12px; font-weight:600; padding:3px 9px; border-radius:var(--r-sm); background:var(--dark-2); color:#E6E4F5}
.fw-ach .xpline{display:flex; justify-content:space-between; font-size:12.5px; font-weight:600; margin:16px 0 6px; color:#B9B7CC}
.fw-ach .xpline b{color:var(--lime)}
.fw-ach .bar{height:6px; border-radius:3px; background:var(--dark-2); overflow:hidden}
.fw-ach .bar span{display:block; height:100%; border-radius:3px; background:var(--lime); width:var(--to)}
.fw-ach .lvlup{display:inline-block; margin-top:12px; font-size:12px; font-weight:700; color:var(--ink); background:var(--lime);
  padding:4px 10px; border-radius:var(--r-sm)}
.fw-confetti{display:none}
@keyframes fw-ach-in{from{opacity:0; transform:translateY(-12px)} to{opacity:1; transform:none}}
@keyframes fw-ach-out{to{opacity:0; visibility:hidden}}
@keyframes fw-xp{from{width:var(--from)} to{width:var(--to)}}
@media (prefers-reduced-motion: no-preference){
  .fw-ach{animation:fw-ach-in .25s ease-out both}
  .fw-ach .bar span{animation:fw-xp .9s cubic-bezier(.2,.7,.2,1) .3s both}
}

/* ---- Streamlit widgets ---- */
.stButton button[kind="primary"]{background:var(--lime); color:var(--ink); border:0; font-weight:700; border-radius:12px; min-height:44px; box-shadow:0 1px 0 rgba(23,23,31,.06), inset 0 -2px 0 rgba(63,90,0,.12)}
.stButton button[kind="primary"]:hover{background:var(--lime-hover); color:var(--ink)}
.stButton button[kind="secondary"]{border-radius:var(--r); border-color:var(--line); color:var(--ink-2)}
.stButton button[kind="secondary"]:hover{border-color:var(--ink-2); color:var(--ink)}
.stButton button[kind="tertiary"]{color:var(--muted)}
.stButton button[kind="tertiary"]:hover{color:var(--bad)}
[data-testid="stTextInputRootElement"], [data-baseweb="select"] > div, [data-testid="stNumberInputContainer"],
[data-testid="stDateInputField"]{background:#F7F6F3 !important; border-radius:10px !important}
[data-testid="stSegmentedControl"] button, [data-testid="stPills"] button{border-radius:var(--r) !important}
[data-testid="stExpander"] details{border-radius:var(--r-lg) !important; border-color:var(--line) !important; background:var(--card)}

/* ---- Product nav ----
   A full-width top bar: brand, page tabs, cycle level. The current page is a
   charcoal tab. When space runs short the tabs drop their labels and show
   icons only (each keeps a tooltip). On phones the tabs move to a bottom bar.
   No transform/filter on the top bar, so the tab group can be fixed to the
   viewport on phones. */
.st-key-fw-topbar{position:fixed; top:0; left:0; right:0; z-index:999990; height:64px; padding:0 max(24px, calc((100vw - 1160px) / 2 + 32px));
  background:var(--card); border-bottom:1px solid rgba(23,23,31,.06); box-shadow:0 6px 20px -16px rgba(48,36,110,.35); flex-wrap:nowrap !important; gap:16px !important}
.st-key-fw-topbar > div{width:auto !important; flex:0 0 auto}
.st-key-fw-topbar > div:has(.st-key-fw-tabs){flex:1 1 auto !important; min-width:0}
.st-key-fw-topbar .stElementContainer:has(> [data-testid="stHtml"] style:only-child){display:none}
.fw-brandmark{display:flex; align-items:center; gap:10px; white-space:nowrap}
.fw-brandmark img{width:30px; height:30px; border-radius:8px}
.fw-brandmark b{font-size:17px; font-weight:800; letter-spacing:-0.02em; color:var(--ink)}
.st-key-fw-tabs{flex:1 1 auto !important; justify-content:center; flex-wrap:nowrap !important; gap:2px !important}
.st-key-fw-tabs > div, .st-key-fw-tabs [class*="st-key-fw-tab-"], .st-key-fw-tabs [class*="st-key-fw-tab-"] > div{width:auto !important; flex:0 0 auto}
.st-key-fw-tabs a{height:38px; padding:0 12px !important; border-radius:var(--r) !important; background:transparent;
  color:var(--muted) !important; gap:8px}
.st-key-fw-tabs a *{color:inherit !important}
.st-key-fw-tabs a p{font-size:14px !important; font-weight:600 !important; white-space:nowrap}
.st-key-fw-tabs a [data-testid="stIconMaterial"]{font-size:20px !important}
.st-key-fw-tabs a:hover{background:var(--sunk); color:var(--ink) !important}
.fw-level{display:flex; align-items:center; gap:10px; white-space:nowrap}
.fw-level .badge{width:30px; height:30px; border-radius:8px; background:var(--dark); color:var(--lime); display:flex;
  align-items:center; justify-content:center; font-weight:700; font-size:13px; font-variant-numeric:tabular-nums}
.fw-level .txt{display:flex; flex-direction:column; gap:5px; min-width:84px}
.fw-level .txt b{font-size:12.5px; font-weight:700; color:var(--ink); line-height:1}
.fw-level .bar{height:4px; border-radius:2px; background:var(--line-2); overflow:hidden}
.fw-level .bar i{display:block; height:100%; background:var(--lav); border-radius:2px}

/* Medium widths: icons only, no text anywhere in the bar */
@media (max-width:1060px){
  .st-key-fw-tabs a{padding:0 !important; width:42px !important; justify-content:center}
  .st-key-fw-tabs a p{display:none !important}
  .fw-level .txt{display:none}
  .fw-brandmark b{display:none}
}
/* Phones: brand + level on top, icon-only tab bar along the bottom */
@media (max-width:760px){
  .st-key-fw-topbar{height:56px; padding:0 16px; justify-content:space-between}
  .fw-brandmark b{display:none}
  [data-testid="stMainBlockContainer"]{padding:80px 16px 104px !important}
  .st-key-fw-tabs{position:fixed !important; left:0; right:0; bottom:0; width:auto !important; height:auto;
    padding:8px 8px calc(8px + env(safe-area-inset-bottom)); box-sizing:border-box;
    background:var(--card); border-top:1px solid var(--line); justify-content:space-around; gap:0 !important}
  .st-key-fw-tabs > div, .st-key-fw-tabs [class*="st-key-fw-tab-"]{flex:1 1 0 !important; display:flex; justify-content:center}
  .st-key-fw-tabs a{width:48px !important; height:44px; border-radius:12px !important}
  .st-key-fw-tabs a [data-testid="stIconMaterial"]{font-size:23px !important}
}
/* ---- Pantry: Add food panel ---- */
.st-key-addform{gap:12px !important; padding:20px !important}
.fw-addhead{display:flex; gap:12px; align-items:center; padding-bottom:14px; border-bottom:1px solid var(--line)}
.fw-addhead .t{font-size:16px; font-weight:700; color:var(--ink); letter-spacing:-0.02em}
.fw-addhead .s{font-size:12.5px; color:var(--muted); margin-top:2px; line-height:1.4}
.fw-addlbl{font-size:12px; font-weight:600; color:var(--muted); margin-bottom:-6px}
.st-key-quickadd{flex-wrap:wrap !important; gap:6px !important}
.st-key-quickadd > div{width:auto !important; flex:0 0 auto}
.st-key-quickadd button{min-height:32px !important; padding:4px 12px !important; border-radius:var(--r) !important;
  border:1px solid var(--line) !important; background:var(--panel) !important; font-size:13px !important}
.st-key-quickadd button:hover{border-color:var(--ink-2) !important; background:var(--card) !important}
.st-key-addform [data-testid="stWidgetLabel"] p{font-size:12.5px !important; font-weight:600 !important; color:var(--muted) !important}

.fw-estimate{background:var(--sunk); border-radius:var(--r); padding:12px 14px}
.fw-estimate .k{display:flex; align-items:center; gap:6px; font-size:12px; font-weight:600; color:var(--muted)}
.fw-estimate .v{display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:6px}
.fw-estimate .v b{font-size:15px; color:var(--ink)}
.fw-estimate .s{font-size:12px; color:var(--muted); margin-top:4px; line-height:1.4}
</style>
"""


def inject_css() -> None:
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


# Short tab labels so six tabs fit a phone bar; page titles keep the full names.
NAV_LABELS = {"Soil & farm": "Farm", "Food & recipes": "Recipes"}


def navbar(pages: list, current: object) -> None:  # list[StreamlitPage], StreamlitPage
    """Product nav: brand, page tabs, cycle level. Built from ``st.page_link`` so
    switching pages stays inside the running app. Streamlit does not mark the
    current link, so each tab sits in a keyed container and one rule lights it."""
    try:
        from larder.achievements import ProgressStore

        progress = ProgressStore().load()
        level, name, pct = progress.level, progress.level_name, progress.level_pct
    except Exception:  # progress is a nicety; never block the nav
        level, name, pct = 1, "Sprout", 0.0
    with st.container(key="fw-topbar", horizontal=True, vertical_alignment="center"):
        st.html('<div class="fw-brandmark"><img src="app/static/fallow-logo-app-192.png" alt=""><b>Fallow</b></div>')
        with st.container(key="fw-tabs", horizontal=True, vertical_alignment="center", gap=None):
            for index, page in enumerate(pages):
                with st.container(key=f"fw-tab-{index}"):
                    st.page_link(page, label=NAV_LABELS.get(page.title, page.title), help=page.title)
                if page == current:
                    st.html(
                        f"<style>.st-key-fw-tab-{index} a{{background:var(--dark) !important; color:#fff !important}}"
                        f".st-key-fw-tab-{index} a [data-testid=stIconMaterial]{{color:var(--lime) !important}}</style>"
                    )
        st.html(
            f'<div class="fw-level" title="Your cycle: {pct:.0f}% to the next level">'
            f'<span class="badge">{level}</span><span class="txt"><b>{escape(name)}</b>'
            f'<span class="bar"><i style="width:{pct:.0f}%"></i></span></span></div>'
        )


def top(title: str, subtitle: str, avatar_icon: str = "eco", search: bool = False) -> None:
    sb = (
        f'<a class="fw-sbtn" href="pantry" target="_self" aria-label="Search your pantry">{icon("search")}</a>'
        if search
        else ""
    )
    st.html(
        f'<div class="fw-top"><div class="fw-lhs"><div class="fw-avatar">{icon(avatar_icon)}</div>'
        f'<div style="min-width:0"><p class="fw-hello">{escape(title)}</p>'
        f'<div class="fw-sub">{escape(subtitle)}</div></div></div>'
        f'<div class="fw-topbtns">{sb}</div></div>'
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
    st.html(f'<div class="fw-stats">{cells}</div>')


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


TONE_PILL = {"good": "lime", "watch": "cream", "alert": "red"}


def _mini(icon_name: str, key: str, value: str, unit: str, label: tuple[str, str] | None) -> str:
    pill = f'<span class="fw-pill {TONE_PILL[label[1]]}">{escape(label[0])}</span>' if label else ""
    return (
        f'<div class="m"><div class="k">{icon(icon_name)}{escape(key)}</div>'
        f'<div class="v">{escape(value)}<small>{escape(unit)}</small></div>{pill}</div>'
    )


_RANK = {"good": 0, "watch": 1, "alert": 2}


def _worst(*labels: tuple[str, str]) -> tuple[str, str]:
    return max(labels, key=lambda label: _RANK[label[1]])


def _pair_tile(icon_name: str, key: str, lines: list[tuple[str, str, str]], label: tuple[str, str]) -> str:
    rows = "".join(
        f'<div class="pair">{icon(i, 15)}<b>{escape(v)}</b><small>{escape(u)}</small></div>' for i, v, u in lines
    )
    return (
        f'<div class="m"><div class="k">{icon(icon_name)}{escape(key)}</div>{rows}'
        f'<span class="fw-pill {TONE_PILL[label[1]]}">{escape(label[0])}</span></div>'
    )


def weather_card(snapshot: SensorSnapshot, mode: str) -> str:
    frost = ("Frost risk", "alert") if snapshot.frost_risk else ("No frost", "good")
    air_lines, air_labels = [], []
    if snapshot.humidity is not None:
        air_lines.append(("humidity_percentage", f"{snapshot.humidity * 100:.0f}", "% humidity"))
    if snapshot.co2_ppm is not None:
        air_lines.append(("co2", f"{snapshot.co2_ppm:.0f}", "ppm CO\u2082"))
        air_labels.append(co2_label(snapshot.co2_ppm))
    safe_lines = [("ac_unit", "Frost" if snapshot.frost_risk else "None", "tonight")]
    safe_labels = [frost]
    if snapshot.radiation_usv_h is not None:
        safe_lines.append(("radiology", f"{snapshot.radiation_usv_h:.2f}", "\u00b5Sv/h"))
        safe_labels.append(radiation_label(snapshot.radiation_usv_h))
    tiles = ""
    if air_lines:
        tiles += _pair_tile("air", "Air", air_lines, _worst(*air_labels) if air_labels else ("Reading", "good"))
    tiles += _pair_tile("shield", "Safety", safe_lines, _worst(*safe_labels))
    source = "Sample reading" if mode == "mock" else "Live"
    return (
        f'<div class="fw-card fw-wx"><div class="chead"><div class="ctitle">{icon("partly_cloudy_day")}Weather</div>'
        f'<span class="fw-pill ghost">{source}</span></div>'
        f'<div class="now"><div class="deg">{snapshot.temp_c:.0f}&deg;</div>'
        f'<div><div class="cond">{escape(snapshot.weather)}</div>'
        f'<div class="small" style="font-size:13px;color:var(--muted)">{escape(snapshot.location)}</div></div></div>'
        f'<div class="fw-mini">{tiles}</div></div>'
    )


def health_card(body: BodySnapshot | None, report: NutritionReport | None = None) -> str:
    cells = []
    if body and body.spo2_pct is not None:
        cells.append(_mini("spo2", "Blood oxygen", f"{body.spo2_pct:.0f}", "%", spo2_label(body.spo2_pct)))
    if body and body.heart_rate_bpm is not None:
        cells.append(_mini("favorite", "Heart rate", f"{body.heart_rate_bpm:.0f}", "bpm", heart_rate_label(body.heart_rate_bpm)))
    vitals = f'<div class="fw-mini">{"".join(cells)}</div>' if cells else '<div class="fw-foot">No watch or oximeter connected.</div>'
    food = ""
    if report is not None:
        total = len(report.groups)
        gap = f" &middot; short on {escape(', '.join(report.gaps))}" if report.gaps else ""
        food = (
            f'<div style="margin-top:14px"><div class="cond" style="font-size:14px;font-weight:700;color:var(--ink)">'
            f'{report.covered} of {total} food groups stocked</div>'
            f'<div style="font-size:12px;color:var(--muted);margin-top:2px">Fresh food, staples, protein{gap}</div>'
            f'<div class="fw-meter3 light" style="max-width:100%">'
            + "".join(f'<span class="{"on" if i < report.covered else ""}"></span>' for i in range(total))
            + "</div></div>"
        )
    source = escape(body.source.capitalize()) if body else "Not connected"
    return (
        f'<div class="fw-card"><div class="chead"><div class="ctitle">{icon("monitor_heart")}Health</div>'
        f'<span class="fw-pill ghost">{source}</span></div>{vitals}{food}'
        '<div class="fw-foot">Wellness info, not medical advice.</div></div>'
    )


def duo(left: str, right: str) -> None:
    st.html(f'<div class="fw-duo">{left}{right}</div>')


CONFETTI_COLORS = ["#D7F26E", "#BBA6F0", "#FCE6DA", "#FFF0D6", "#8DC63F", "#FFFFFF", "#F29B4B"]


def achievement_popup(reward: Reward) -> None:
    """Game-style popup: badge spin, shine, confetti burst, XP bar fill. Tap x to close; fades out on its own."""
    import random

    rng = random.Random(reward.xp_after)
    confetti = "".join(
        f'<span class="fw-confetti" style="background:{rng.choice(CONFETTI_COLORS)};'
        f"--x:{rng.randint(-170, 170)}px;--y:{rng.randint(-120, 210)}px;--r:{rng.randint(-540, 540)}deg;"
        f'animation-delay:{0.25 + rng.random() * 0.35:.2f}s"></span>'
        for _ in range(28)
    )
    if reward.unlocked:
        first = reward.unlocked[0]
        eyebrow, title, desc, glyph = "Achievement unlocked", first.title, first.description, first.icon
        more = "".join(f"<span>{escape(a.title)}</span>" for a in reward.unlocked[1:])
        more = f'<div class="more">{more}</div>' if more else ""
    else:
        eyebrow, title, desc, glyph, more = "Nice work", reward.action, "Progress saved.", "check", ""
    start = 0 if reward.leveled_up else (reward.xp_before % XP_PER_LEVEL) / XP_PER_LEVEL * 100
    end = (reward.xp_after % XP_PER_LEVEL) / XP_PER_LEVEL * 100 or (100 if reward.xp_after else 0)
    lvlup = f'<div class="lvlup">Level up! Level {reward.level_after}</div>' if reward.leveled_up else ""
    st.html(
        '<div class="fw-ach-wrap" role="status" aria-live="polite"><div class="fw-ach">'
        f'<label class="x" aria-label="Close">{icon("close")}<input type="checkbox"></label>'
        f"{confetti}"
        f'<div class="fw-ach-badge">{icon(glyph)}<span class="shine"></span></div>'
        f'<div class="eyebrow">{eyebrow}</div><div class="title">{escape(title)}</div>'
        f'<div class="desc">{escape(desc)}</div>{more}'
        f'<div class="xpline"><b>+{reward.xp_gained} XP</b><span>Level {reward.level_after}</span></div>'
        f'<div class="bar"><span style="--from:{start:.0f}%;--to:{end:.0f}%"></span></div>{lvlup}'
        "</div></div>"
    )


def cycle_card(progress: Progress) -> None:
    steps = [("skillet", "Cook what spoils", "recipes"), ("monitor_heart", "Check health", "health"), ("potted_plant", "Plant the gap", "farm")]
    done = progress.cycle
    next_i = next((i for i, d in enumerate(done) if not d), None)
    filled = sum(done) / len(done) * 100 if len(done) > 1 else 0
    cells = []
    for i, (ic, label, href) in enumerate(steps):
        state = "done" if done[i] else ("next" if i == next_i else "")
        chk = f'<span class="chk">{icon("check")}</span>' if done[i] else ""
        cells.append(
            f'<a class="fw-step {state}" href="{href}" target="_self"><span class="dot">{icon(ic)}{chk}</span>'
            f'<span class="lbl">{escape(label)}</span></a>'
        )
    badges = "".join(
        f'<div class="fw-badge {"on" if a.id in progress.unlocked else ""}" title="{escape(a.title)}: {escape(a.description)}">'
        f'{icon(a.icon if a.id in progress.unlocked else "lock", 22)}</div>'
        for a in CATALOG
    )
    into = progress.xp % XP_PER_LEVEL
    st.html(
        '<div class="fw-card"><div class="chead"><div class="ctitle">' + icon("cycle") + "Your cycle</div>"
        f'<span class="fw-pill lime">Level {progress.level} &middot; {escape(progress.level_name)}</span></div>'
        f'<div class="fw-cycle"><div class="line"><span style="width:{filled:.0f}%"></span></div>{"".join(cells)}</div>'
        f'<div class="fw-xp"><span><b>{progress.xp} XP</b> total</span><span>{into} / {XP_PER_LEVEL} to level {progress.level + 1}</span></div>'
        f'<div class="fw-xpbar"><span style="width:{into / XP_PER_LEVEL * 100:.0f}%"></span></div>'
        f'<div class="fw-badges">{badges}</div>'
        f'<div class="fw-foot">{len(progress.unlocked)} of {len(CATALOG)} achievements</div></div>'
    )
