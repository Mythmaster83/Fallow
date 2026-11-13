"""Static shelf-life table used when an item has no expiry date.

Numbers are typical days from the day you brought the food home. A named
food overrides its category. Unknown foods fall back to two weeks, which is
deliberately short so the planner would rather cook early than throw food out.
"""

from __future__ import annotations

# Days the food usually lasts in ordinary home storage.
CATEGORY_DAYS: dict[str, int] = {
    "leafy_greens": 5,
    "produce": 7,
    "berries": 3,
    "dairy": 10,
    "meat": 3,
    "fish": 2,
    "eggs": 21,
    "bread": 5,
    "leftovers": 3,
    "grain": 365,
    "pantry": 365,
    "frozen": 90,
    "herb": 7,
}

# Named foods win over the category when both exist.
ITEM_DAYS: dict[str, int] = {
    "spinach": 4,
    "lettuce": 5,
    "kale": 7,
    "tomatoes": 6,
    "bananas": 5,
    "apples": 21,
    "carrots": 21,
    "potatoes": 60,
    "onions": 30,
    "milk": 7,
    "yogurt": 14,
    "cheese": 21,
    "chicken": 2,
    "ground beef": 2,
    "salmon": 2,
    "eggs": 21,
    "bread": 5,
    "tofu": 7,
    "rice": 365,
    "beans": 365,
    "lentils": 365,
    "pasta": 365,
}


def baseline_days(name: str, category: str) -> int:
    """Return the table's shelf life, in days, for this food."""
    item_key = name.strip().lower()
    if item_key in ITEM_DAYS:
        return ITEM_DAYS[item_key]
    category_key = category.strip().lower().replace(" ", "_").replace("-", "_")
    if category_key in CATEGORY_DAYS:
        return CATEGORY_DAYS[category_key]
    return 14
