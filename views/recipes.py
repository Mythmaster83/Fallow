"""Food and recipes: step-by-step meals from food already on hand."""

from __future__ import annotations

from html import escape

import streamlit as st

import fallow_ui as ui
from larder.llm.client import LLMClient
from larder.meals.planner import plan_meals
from larder.meals.recipes import cook, recipe_for
from larder.spoilage.predictor import predict_spoilage
from larder.store import open_store

store = open_store()
items = store.list_items()
risks = predict_spoilage(items, client=LLMClient.from_env())
plan = plan_meals(items, risks=risks)
recipes = [recipe_for(meal, items) for meal in plan.meals]

ui.top("Food & recipes", f"{ui.today_label()} · cook what spoils first", avatar_icon="restaurant_menu")

flash = st.session_state.pop("recipes_flash", None)
if flash:
    st.success(flash, icon=":material/check_circle:")


def _cooked(index: int) -> None:
    recipe = recipes[index]
    for item in cook(recipe, items):
        store.upsert(item)
    st.session_state.recipes_flash = f"Cooked: {recipe.name}. Pantry amounts updated."


if recipes:
    first = recipes[0]
    st.html(
        f'<div class="fw-feature"><div class="eyebrow">{ui.icon("bolt", 18)}Cook today</div>'
        f'<div class="title">{escape(first.name)}</div>'
        f'<div class="desc">About {first.minutes} min, using {escape(", ".join(i.name for i in first.ingredients))}.</div>'
        f'<a class="cta" href="#day-1" target="_self">Start cooking</a>'
        f'<div class="blob">{ui.icon("skillet")}</div></div>'
    )
    ui.heading("Your plan", pill=f"Next {plan.horizon_days} days")
    cols = st.columns(min(len(recipes), 3), gap="medium")
    for index, recipe in enumerate(recipes):
        with cols[index % len(cols)]:
            st.html(f'<div id="day-{recipe.day}"></div>')
            with st.container(key=f"card-recipe-{index}"):
                ui.recipe_card(recipe, tone=ui.TILE_TONES[index % len(ui.TILE_TONES)])
                st.button(
                    "Mark as cooked",
                    key=f"cook-{index}",
                    type="primary",
                    icon=":material/check:",
                    on_click=_cooked,
                    args=(index,),
                    width="stretch",
                )
    st.caption("Marking a meal cooked uses up the main food and one portion of the staple.")
else:
    ui.feature("All clear", "Nothing needs cooking yet", plan.summary, "Open pantry", "pantry", "verified")
