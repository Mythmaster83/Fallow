"""Turn a planned meal into simple steps, and mark a meal as cooked.

Steps are plain templates keyed by the category of the food that is about
to spoil. Every ingredient comes from the inventory: a recipe never adds a
shopping item. Cooking uses up the urgent food and one portion of the staple.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from larder.lifecycle import advance
from larder.models import CycleEvent, InventoryItem, PlannedMeal, Transition

# One serving of a staple, by unit. Anything not listed uses 1.
PORTION = {"kg": 0.25, "g": 250, "lb": 0.5, "oz": 8, "loaf": 0.5, "quart": 0.25, "l": 0.25}

_STAPLE_PREP = {
    "grain": "Rinse the {staple} and simmer it covered until tender, about 15 to 20 minutes.",
    "pantry": "Drain and rinse the {staple}, then warm them in a pan with a splash of water.",
    "bread": "Slice and toast the {staple}.",
}

_MAIN_STEPS: dict[str, tuple[int, list[str]]] = {
    "leafy_greens": (20, [
        "Wash the {item} and shake it dry.",
        "Wilt it in a hot pan with a little oil and salt for 2 to 3 minutes.",
    ]),
    "produce": (35, [
        "Cut the {item} into even pieces.",
        "Roast at 425°F (220°C) with oil and salt for 25 to 30 minutes, turning once.",
    ]),
    "berries": (10, [
        "Rinse the {item} and drop any soft ones.",
        "Eat them fresh, or simmer 5 minutes with a little sugar for a quick compote.",
    ]),
    "meat": (30, [
        "Cut the {item} into bite-size pieces and season with salt and pepper.",
        "Sear in a hot skillet with oil until cooked through (poultry to 165°F / 74°C).",
    ]),
    "fish": (20, [
        "Pat the {item} dry and season it.",
        "Pan-sear 3 to 4 minutes per side until it flakes (145°F / 63°C).",
    ]),
    "dairy": (15, [
        "Warm the {item} gently; do not let it boil.",
        "Stir it into the base for a creamy porridge or sauce.",
    ]),
    "eggs": (10, [
        "Beat the {item} with a pinch of salt.",
        "Scramble over low heat, adding any soft vegetables you have.",
    ]),
    "bread": (15, [
        "Slice the {item}.",
        "Toast it, or cube it and bake at 375°F (190°C) for 10 minutes into croutons.",
    ]),
    "leftovers": (15, [
        "Reheat the {item} in a skillet until steaming hot all the way through.",
    ]),
    "herb": (10, [
        "Chop the {item} finely.",
        "Fold it through the warm base with oil and salt.",
    ]),
}


class Ingredient(BaseModel):
    item_id: str
    name: str
    amount: float
    unit: str


class Recipe(BaseModel):
    day: int
    name: str
    minutes: int
    ingredients: list[Ingredient]
    steps: list[str]
    why: str


def staple_portion(item: InventoryItem) -> float:
    return min(item.quantity, PORTION.get(item.unit.strip().lower(), 1))


def recipe_for(meal: PlannedMeal, items: list[InventoryItem]) -> Recipe:
    """Steps and amounts for one planned meal, using only inventory food."""
    by_id = {item.id: item for item in items}
    present = [by_id[i] for i in meal.item_ids if i in by_id]
    if not present:
        return Recipe(day=meal.day, name=meal.name, minutes=0, ingredients=[], steps=[], why=meal.why)
    main, staples = present[0], present[1:]

    minutes, main_steps = _MAIN_STEPS.get(
        main.category, (20, ["Cook the {item} through."])
    )
    ingredients = [Ingredient(item_id=main.id, name=main.name, amount=main.quantity, unit=main.unit)]
    steps: list[str] = []
    for staple in staples:
        ingredients.append(
            Ingredient(item_id=staple.id, name=staple.name, amount=staple_portion(staple), unit=staple.unit)
        )
        prep = _STAPLE_PREP.get(staple.category)
        if prep:
            steps.append(prep.format(staple=staple.name))
    steps.extend(step.format(item=main.name) for step in main_steps)
    if staples:
        steps.append(f"Serve the {main.name} with the {', '.join(s.name for s in staples)}.")
    return Recipe(
        day=meal.day, name=meal.name, minutes=minutes, ingredients=ingredients, steps=steps, why=meal.why
    )


def cook(recipe: Recipe, items: list[InventoryItem]) -> list[InventoryItem]:
    """Return the items whose quantity changes when this recipe is cooked."""
    by_id = {item.id: item for item in items}
    changed: list[InventoryItem] = []
    for ingredient in recipe.ingredients:
        item = by_id.get(ingredient.item_id)
        if item is None:
            continue
        left = max(0.0, round(item.quantity - ingredient.amount, 3))
        changed.append(item.model_copy(update={"quantity": left}))
    return changed


def cook_meal(recipe: Recipe, items: list[InventoryItem], today: date) -> Transition:
    """Cook and eat a recipe through the lifecycle.

    The main food goes raw → cooked → consumed, and its trimmings become
    scraps for the compost. Each staple loses one portion and stays on the
    shelf. Every change is logged, so the Cycle page shows the meal.
    """
    by_id = {item.id: item for item in items}
    saved: list[InventoryItem] = []
    events: list[CycleEvent] = []
    for index, ingredient in enumerate(recipe.ingredients):
        item = by_id.get(ingredient.item_id)
        if item is None or not item.is_food:
            continue
        if index == 0:
            if item.state != "cooked":
                cooked = advance(item, "cooked", today, note=recipe.name)
                saved.extend(cooked.items[1:])  # scraps
                events.extend(cooked.events)
                item = cooked.items[0]
            eaten = advance(item, "consumed", today, note=recipe.name)
            saved.insert(0, eaten.items[0])
            events.extend(eaten.events)
            continue
        left = max(0.0, round(item.quantity - ingredient.amount, 3))
        saved.append(item.model_copy(update={"quantity": left}))
        events.append(
            CycleEvent(
                item_id=item.id,
                item_name=item.name,
                from_state=item.state,
                to_state=item.state,
                location=item.location,
                on=today,
                note=f"used {item.quantity - left:g} {item.unit} in {recipe.name}",
            )
        )
    return Transition(items=saved, events=events)
