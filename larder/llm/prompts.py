"""Prompt text for the spoilage model.

The meal planner and the grow advisor stay rule-based so they work with no
network. This module is only the spoilage question: what will go bad first?
"""

from __future__ import annotations

import json
from datetime import date

from larder.models import InventoryItem
from larder.spoilage.shelf_life import baseline_days


def spoilage_messages(items: list[InventoryItem], today: date) -> tuple[str, str]:
    """Build the system and user messages for one spoilage request."""
    catalog = [
        {
            "item_id": item.id,
            "item_name": item.name,
            "category": item.category,
            "quantity": item.quantity,
            "unit": item.unit,
            "location": item.location,
            "acquired_on": item.acquired_on.isoformat(),
            "expires_on": item.expires_on.isoformat() if item.expires_on else None,
            "baseline_shelf_life_days": baseline_days(item.name, item.category),
        }
        for item in items
    ]
    system = (
        "You estimate which foods in a home kitchen will spoil first. "
        "Reply with one JSON object and nothing else. "
        "Use only item_id values from the inventory. Do not invent foods."
    )
    user = (
        f"Today is {today.isoformat()}.\n"
        "risk must be one of: low, medium, high, critical.\n"
        "days_remaining is an integer. Use a negative number when the food is already overdue.\n"
        'Set source to "llm" on every row.\n'
        "JSON shape:\n"
        '{"risks":[{"item_id":"","item_name":"","risk":"low","days_remaining":0,'
        '"reason":"","source":"llm"}]}\n'
        f"Inventory:\n{json.dumps(catalog)}"
    )
    return system, user
