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
