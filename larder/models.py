"""Domain models shared by the pantry, the meal planner, and the garden.

An inventory item is one thing in the kitchen. A spoilage risk says how soon
that thing goes bad. A meal plan cooks what you already have. A grow plan
says what to plant so the next gap in the pantry does not become a shortage.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["low", "medium", "high", "critical"]
RiskSource = Literal["llm", "heuristic"]

# Where a thing is in the dirt-to-plate-and-back loop.
LifecycleState = Literal[
    "seed",
    "growing",
    "harvested",
    "raw",
    "opened",
    "cooked",
    "consumed",
    "trashed",
    "scraps",
    "compost",
    "soil_amendment",
    "applied",
]

# States in which the thing is food you can eat. Only these count toward
# spoilage, meal plans, and pantry reserves.
FOOD_STATES: frozenset[str] = frozenset({"harvested", "raw", "opened", "cooked"})

# Places a thing can sit. Moving between them recalculates expiry.
STORAGE_LOCATIONS: tuple[str, ...] = (
    "fridge",
    "freezer",
    "pantry",
    "counter",
    "root cellar",
    "ground",
    "compost bin",
)


class InventoryItem(BaseModel):
    """One ingredient or staple on hand."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    quantity: float = Field(ge=0)
    unit: str = Field(min_length=1)
    acquired_on: date
    expires_on: date | None = None
    location: str = "pantry"
    state: LifecycleState = "raw"
    state_since: date | None = None
    parent_id: str | None = None

    @property
    def is_food(self) -> bool:
        """True while this is edible food on hand (not seed, scraps, or soil)."""
        return self.state in FOOD_STATES and self.quantity > 0


class CycleEvent(BaseModel):
    """One step an item took through the lifecycle or between storage spots."""

    item_id: str
    item_name: str
    from_state: LifecycleState | None
    to_state: LifecycleState
    location: str
    on: date
    note: str = ""


class Transition(BaseModel):
    """The result of moving one item: rows to save and events to log.

    ``items`` holds the updated item first, then anything the step produced
    (for example the scraps left over from cooking).
    """

    items: list[InventoryItem]
    events: list[CycleEvent]


class SpoilageRisk(BaseModel):
    """How soon one inventory item is expected to spoil."""

    item_id: str
    item_name: str
    risk: RiskLevel
    days_remaining: int
    reason: str
    source: RiskSource


class PlannedMeal(BaseModel):
    """One meal that uses only food already in the inventory."""

    day: int = Field(ge=1)
    name: str
    item_ids: list[str]
    uses: list[str]
    why: str


class MealPlan(BaseModel):
    """A short cooking plan aimed at the food that will spoil first."""

    horizon_days: int = Field(ge=1)
    meals: list[PlannedMeal]
    priority_item_ids: list[str]
    summary: str


class GrowCrop(BaseModel):
    """One planting suggestion."""

    crop: str
    action: Literal["plant now", "wait"]
    reason: str
    fills: Literal["fresh food", "calorie staples", "protein"]


class GrowPlan(BaseModel):
    """What to plant, and which pantry gaps that planting steadies."""

    location: str
    crops: list[GrowCrop]
    gaps: list[str]
    balance_notes: str
    soil_notes: str = ""
