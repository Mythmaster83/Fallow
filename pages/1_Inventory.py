"""Add, review, and remove pantry items."""

from __future__ import annotations

import re
import uuid
from datetime import date

import streamlit as st

from larder.llm.client import LLMClient, load_project_env
from larder.spoilage.predictor import predict_spoilage
from larder.spoilage.shelf_life import CATEGORY_DAYS
from larder.store import open_store
from larder.models import STORAGE_LOCATIONS, InventoryItem

load_project_env()
st.set_page_config(page_title="Inventory · Fallow", page_icon="🥫", layout="wide")

st.title("Inventory")
st.caption(
    "This is the food on hand. The first time the database is created it is filled "
    "from fixtures/inventory.sample.json. Delete data/fallow.db to load that sample again."
)

store = open_store()
items = store.list_items()

st.subheader("On hand")
if items:
    st.dataframe(
        [
            {
                "name": item.name,
                "category": item.category,
                "quantity": item.quantity,
                "unit": item.unit,
                "state": item.state.replace("_", " "),
                "where": item.location,
                "acquired": item.acquired_on.isoformat(),
                "expires": item.expires_on.isoformat() if item.expires_on else "",
            }
            for item in items
        ],
        width="stretch",
        hide_index=True,
    )
else:
    st.info("Nothing stored. Add the first item below.")

risks = predict_spoilage(items, client=LLMClient.from_env())
if risks:
    st.subheader("Spoilage")
    st.caption("Only edible food is ranked. Crops in the ground and compost live on the Cycle page.")
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

st.subheader("Add food")
with st.form("add-item", clear_on_submit=True):
    name = st.text_input("Name", placeholder="spinach")
    category = st.selectbox("Category", sorted(CATEGORY_DAYS))
    quantity = st.number_input("Quantity", min_value=0.0, value=1.0, step=0.5)
    unit = st.text_input("Unit", value="count")
    location = st.selectbox(
        "Where it is", [loc for loc in STORAGE_LOCATIONS if loc not in {"ground", "compost bin"}]
    )
    acquired_on = st.date_input("Acquired on", value=date.today())
    expires_known = st.checkbox("I know the expiry date", value=False)
    expires_on = st.date_input("Expires on", value=date.today())
    submitted = st.form_submit_button("Add to inventory")

if submitted:
    cleaned = name.strip()
    if not cleaned:
        st.error("Give the food a name.")
    elif quantity <= 0:
        st.error("Quantity has to be greater than zero.")
    elif not unit.strip():
        st.error("Give the quantity a unit, such as lb, bag, or count.")
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", cleaned.lower()).strip("-") or "item"
        store.upsert(
            InventoryItem(
                id=f"{slug}-{uuid.uuid4().hex[:4]}",
                name=cleaned,
                category=category,
                quantity=float(quantity),
                unit=unit.strip(),
                acquired_on=acquired_on,
                expires_on=expires_on if expires_known else None,
                location=location,
            )
        )
        st.success(f"Added {cleaned}.")
        st.rerun()

st.subheader("Remove food")
if not items:
    st.caption("Nothing to remove.")
else:
    labels = {f"{item.name} ({item.id})": item.id for item in items}
    choice = st.selectbox("Item", list(labels))
    if st.button("Remove"):
        store.delete(labels[choice])
        st.rerun()
