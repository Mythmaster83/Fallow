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
from larder.health.vitals import BodySnapshot, co2_label, heart_rate_label, radiation_label, spo2_label
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
@media (max-width:900px){.fw-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
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
/* weather + health cards */
.fw-duo{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin-top:12px}
@media (max-width:900px){.fw-duo{grid-template-columns:1fr}}
.fw-card .chead{display:flex; justify-content:space-between; align-items:center; gap:8px}
.fw-card .ctitle{font-size:18px; font-weight:700; color:var(--ink); display:flex; align-items:center; gap:8px}
.fw-wx .now{display:flex; align-items:center; gap:14px; margin:14px 0 4px}
.fw-wx .deg{font-size:46px; font-weight:800; letter-spacing:-0.04em; color:var(--ink); line-height:1}
.fw-wx .cond{font-size:15px; font-weight:700; color:var(--ink)}
.fw-mini{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; margin-top:14px}
.fw-mini .m{background:var(--panel); border-radius:16px; padding:12px}
.fw-mini .k{font-size:12px; color:var(--muted); display:flex; align-items:center; gap:6px}
.fw-mini .k .ms{font-size:16px}
.fw-mini .v{font-size:18px; font-weight:800; color:var(--ink); margin:6px 0 6px; letter-spacing:-0.02em}
.fw-mini .v small{font-size:12px; font-weight:600; color:var(--muted); margin-left:3px}
.fw-meter3.light span{background:var(--panel)}
.fw-meter3.light span.on{background:#8DC63F}
.fw-foot{font-size:12px; color:var(--muted); margin-top:12px}
/* achievements: popup, cycle stepper, badges */
.fw-ach-wrap{position:fixed; inset:0; z-index:999999; display:flex; align-items:flex-start; justify-content:center;
  padding-top:90px; pointer-events:none; animation:fw-ach-out .45s ease-in 6.5s forwards}
.fw-ach-wrap:has(input:checked){display:none}
.fw-ach{pointer-events:auto; position:relative; width:min(340px,88vw); background:var(--dark); color:#fff; border-radius:28px;
  padding:26px 22px 20px; text-align:center; box-shadow:0 30px 70px -20px rgba(30,20,80,.6); overflow:visible}
.fw-ach .x{position:absolute; top:10px; right:12px; width:36px; height:36px; border-radius:50%; display:flex;
  align-items:center; justify-content:center; color:#CFCDE0; cursor:pointer}
.fw-ach .x input{position:absolute; opacity:0; width:0; height:0}
.fw-ach-badge{width:92px; height:92px; margin:-70px auto 10px; border-radius:50%; background:var(--lime); color:var(--dark);
  display:flex; align-items:center; justify-content:center; position:relative; overflow:hidden; box-shadow:0 0 0 6px var(--dark), 0 0 0 9px #D7F26E55}
.fw-ach-badge .ms{font-size:44px}
.fw-ach-badge .shine{position:absolute; top:-20%; left:-60%; width:40%; height:140%; background:rgba(255,255,255,.55); transform:rotate(25deg)}
.fw-ach .eyebrow{font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:var(--lime); font-weight:800}
.fw-ach .title{font-size:24px; font-weight:800; letter-spacing:-0.02em; margin:6px 0 4px}
.fw-ach .desc{font-size:13px; color:#B7B5C9; line-height:1.45}
.fw-ach .more{display:flex; flex-wrap:wrap; justify-content:center; gap:6px; margin-top:10px}
.fw-ach .more span{font-size:11px; font-weight:700; padding:4px 10px; border-radius:999px; background:#2B2B3B; color:#E6E4F5}
.fw-ach .xpline{display:flex; justify-content:space-between; font-size:12px; font-weight:700; margin:16px 0 6px; color:#CFCDE0}
.fw-ach .xpline b{color:var(--lime); font-size:14px}
.fw-ach .bar{height:10px; border-radius:5px; background:#2B2B3B; overflow:hidden}
.fw-ach .bar span{display:block; height:100%; border-radius:5px; background:var(--lime); width:var(--to)}
.fw-ach .lvlup{display:inline-block; margin-top:12px; font-size:12px; font-weight:800; color:var(--dark); background:var(--lime);
  padding:5px 12px; border-radius:999px}
.fw-confetti{position:absolute; left:50%; top:30px; width:9px; height:14px; border-radius:2px; opacity:0}
.fw-cycle{display:flex; align-items:flex-start; justify-content:space-between; position:relative; margin:18px 4px 6px}
.fw-cycle .line{position:absolute; top:23px; left:12%; right:12%; height:4px; border-radius:2px; background:var(--panel)}
.fw-cycle .line span{display:block; height:100%; border-radius:2px; background:#8DC63F}
.fw-step{position:relative; z-index:1; flex:1; display:flex; flex-direction:column; align-items:center; gap:8px; text-decoration:none; color:var(--ink)}
.fw-step .dot{width:50px; height:50px; border-radius:50%; background:var(--panel); color:var(--muted); display:flex; align-items:center;
  justify-content:center; position:relative; transition:transform .2s ease}
.fw-step:hover .dot{transform:scale(1.08) rotate(-4deg)}
.fw-step.done .dot{background:var(--lime); color:var(--dark)}
.fw-step.next .dot{background:var(--dark); color:var(--lime)}
.fw-step .chk{position:absolute; right:-2px; bottom:-2px; width:20px; height:20px; border-radius:50%; background:var(--dark); color:var(--lime);
  display:flex; align-items:center; justify-content:center; box-shadow:0 0 0 2px #fff}
.fw-step .chk .ms{font-size:14px}
.fw-step .lbl{font-size:12px; font-weight:700; text-align:center; line-height:1.25}
.fw-badges{display:grid; grid-template-columns:repeat(8,minmax(0,1fr)); gap:8px; margin-top:14px}
@media (max-width:640px){.fw-badges{grid-template-columns:repeat(4,minmax(0,1fr))}}
.fw-badge{aspect-ratio:1; border-radius:16px; display:flex; align-items:center; justify-content:center; background:var(--panel);
  color:#B9B8C6; transition:transform .2s ease; perspective:200px}
.fw-badge.on{background:var(--t-lime); color:var(--lime-ink)}
.fw-badge.on:nth-child(3n+2){background:var(--t-lav); color:#3D358F}
.fw-badge.on:nth-child(3n){background:var(--t-peach); color:#8A3B12}
.fw-badge:hover{transform:translateY(-3px) rotateY(18deg)}
.fw-xp{display:flex; justify-content:space-between; font-size:12px; color:var(--muted); margin-top:14px}
.fw-xp b{color:var(--ink)}
.fw-xpbar{height:10px; border-radius:5px; background:var(--panel); overflow:hidden; margin-top:6px}
.fw-xpbar span{display:block; height:100%; border-radius:5px; background:var(--dark)}
@keyframes fw-ach-in{0%{opacity:0; transform:translateY(-30px) scale(.8)} 60%{opacity:1; transform:translateY(4px) scale(1.04)} 100%{transform:none}}
@keyframes fw-ach-out{to{opacity:0; visibility:hidden}}
@keyframes fw-spin-in{0%{transform:scale(0) rotate(-200deg)} 70%{transform:scale(1.15) rotate(10deg)} 100%{transform:scale(1) rotate(0)}}
@keyframes fw-shine{0%{left:-60%} 100%{left:140%}}
@keyframes fw-xp{from{width:var(--from)} to{width:var(--to)}}
@keyframes fw-burst{0%{opacity:1; transform:translate(0,0) rotate(0)} 100%{opacity:0; transform:translate(var(--x),var(--y)) rotate(var(--r))}}
@keyframes fw-pulse{0%{box-shadow:0 0 0 0 rgba(215,242,110,.7)} 100%{box-shadow:0 0 0 14px rgba(215,242,110,0)}}
@keyframes fw-glow{0%,100%{box-shadow:0 0 0 6px var(--dark), 0 0 0 9px #D7F26E55} 50%{box-shadow:0 0 0 6px var(--dark), 0 0 0 16px #D7F26E33}}
@media (prefers-reduced-motion: no-preference){
  .fw-ach{animation:fw-ach-in .6s cubic-bezier(.2,.8,.2,1) both}
  .fw-ach-badge{animation:fw-spin-in .8s cubic-bezier(.2,.8,.2,1) .15s both, fw-glow 1.6s ease-in-out 1s infinite}
  .fw-ach-badge .shine{animation:fw-shine 1.1s ease-in-out .8s both}
  .fw-ach .bar span{animation:fw-xp 1.2s cubic-bezier(.2,.7,.2,1) .7s both}
  .fw-ach .lvlup{animation:fw-pop .5s ease-out 1.8s both}
  .fw-confetti{animation:fw-burst 1.4s cubic-bezier(.15,.7,.3,1) both}
  .fw-step.next .dot{animation:fw-pulse 1.4s ease-out infinite}
}
/* motion: slide-in, staggered; off when the device asks for reduced motion */
@keyframes fw-slide{from{opacity:0; transform:translateY(16px)} to{opacity:1; transform:none}}
@keyframes fw-slide-x{from{opacity:0; transform:translateX(28px)} to{opacity:1; transform:none}}
@keyframes fw-grow{from{transform:scaleY(0)} to{transform:scaleY(1)}}
@keyframes fw-fill{from{transform:scaleX(0)} to{transform:scaleX(1)}}
@keyframes fw-pop{0%{transform:scale(.6); opacity:0} 70%{transform:scale(1.08)} 100%{transform:scale(1); opacity:1}}
@media (prefers-reduced-motion: no-preference){
  .fw-top,.fw-search,.fw-feature,.fw-h,.fw-stat,.fw-card,.fw-row,.fw-cond,.fw-group-card,.fw-note,.fw-empty,
  [class*="st-key-card-"],.st-key-addform{animation:fw-slide .55s cubic-bezier(.2,.7,.2,1) both}
  .fw-search{animation-delay:.05s} .fw-feature{animation-delay:.1s}
  .fw-feature .blob{animation:fw-slide-x .7s cubic-bezier(.2,.7,.2,1) .25s both}
  .fw-feature .cta{animation:fw-pop .45s ease-out .45s both}
  .fw-avatar{animation:fw-pop .5s ease-out .1s both}
  .fw-stats>*:nth-child(2),.fw-rows>*:nth-child(2),.fw-duo>*:nth-child(2),.fw-conds>*:nth-child(2),.fw-groups>*:nth-child(2),.fw-group>.fw-row:nth-child(2){animation-delay:.08s}
  .fw-stats>*:nth-child(3),.fw-rows>*:nth-child(3),.fw-conds>*:nth-child(3),.fw-groups>*:nth-child(3),.fw-group>.fw-row:nth-child(3){animation-delay:.16s}
  .fw-stats>*:nth-child(4),.fw-rows>*:nth-child(4),.fw-conds>*:nth-child(4){animation-delay:.24s}
  .fw-rows>*:nth-child(5){animation-delay:.32s}
  .fw-chart .bar{transform-origin:bottom; animation:fw-grow .7s cubic-bezier(.2,.7,.2,1) .2s both}
  .fw-chart .col:nth-child(2) .bar{animation-delay:.26s} .fw-chart .col:nth-child(3) .bar{animation-delay:.32s}
  .fw-chart .col:nth-child(4) .bar{animation-delay:.38s} .fw-chart .col:nth-child(5) .bar{animation-delay:.44s}
  .fw-chart .col:nth-child(6) .bar{animation-delay:.5s} .fw-chart .col:nth-child(7) .bar{animation-delay:.56s}
  .fw-chart .tip{animation:fw-pop .4s ease-out .9s both}
  .fw-meter3 span.on,.fw-cond .gauge span{transform-origin:left; animation:fw-fill .7s cubic-bezier(.2,.7,.2,1) .35s both}
  .fw-row,.fw-stat,.fw-crop,.fw-feature .cta,.fw-search{transition:transform .2s ease, box-shadow .2s ease}
  .fw-row:hover,.fw-stat:hover{transform:translateY(-2px); box-shadow:0 10px 24px -14px rgba(60,40,120,.35)}
  .fw-feature .cta:hover{transform:translateY(-1px) scale(1.03)}
}
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


def weather_card(snapshot: SensorSnapshot, mode: str) -> str:
    frost = ("Frost risk", "alert") if snapshot.frost_risk else ("No frost", "good")
    cells = [
        _mini("humidity_percentage", "Humidity", f"{snapshot.humidity * 100:.0f}" if snapshot.humidity is not None else "n/a",
              "%" if snapshot.humidity is not None else "", None),
        _mini("ac_unit", "Frost", "Tonight", "", frost),
    ]
    if snapshot.co2_ppm is not None:
        cells.append(_mini("co2", "Air CO\u2082", f"{snapshot.co2_ppm:.0f}", "ppm", co2_label(snapshot.co2_ppm)))
    if snapshot.radiation_usv_h is not None:
        cells.append(
            _mini("radiology", "Radiation", f"{snapshot.radiation_usv_h:.2f}", "\u00b5Sv/h", radiation_label(snapshot.radiation_usv_h))
        )
    source = "Sample reading" if mode == "mock" else "Live"
    return (
        f'<div class="fw-card fw-wx"><div class="chead"><div class="ctitle">{icon("partly_cloudy_day")}Weather</div>'
        f'<span class="fw-pill ghost">{source}</span></div>'
        f'<div class="now"><div class="deg">{snapshot.temp_c:.0f}&deg;</div>'
        f'<div><div class="cond">{escape(snapshot.weather)}</div>'
        f'<div class="small" style="font-size:13px;color:var(--muted)">{escape(snapshot.location)}</div></div></div>'
        f'<div class="fw-mini">{"".join(cells)}</div></div>'
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
