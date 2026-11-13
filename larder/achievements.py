"""Progress through the Fallow cycle: cook what spoils, check health, plant the gap.

Cooking and planting earn XP and unlock achievements. Progress lives in the
same SQLite file as the inventory, in its own table, so deleting
``data/fallow.db`` resets both.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel, Field

from larder.meals.recipes import Recipe
from larder.models import GrowCrop, SpoilageRisk
from larder.store import default_db_path

XP_PER_LEVEL = 100
LEVEL_NAMES = ["Sprout", "Forager", "Homesteader", "Survivor", "Fallow master"]


class Achievement(BaseModel):
    id: str
    title: str
    description: str
    icon: str


CATALOG: list[Achievement] = [
    Achievement(id="first_rescue", title="First rescue", description="Cook your first meal from food about to spoil.", icon="skillet"),
    Achievement(id="last_minute", title="Last-minute save", description="Cook food on the day it expires.", icon="timer"),
    Achievement(id="plan_complete", title="Plan complete", description="Cook three planned meals.", icon="restaurant_menu"),
    Achievement(id="zero_waste", title="Zero waste", description="Leave nothing at critical or high risk.", icon="recycling"),
    Achievement(id="health_check", title="Checkup", description="Look at your food health.", icon="monitor_heart"),
    Achievement(id="green_thumb", title="Green thumb", description="Plant your first crop.", icon="potted_plant"),
    Achievement(id="gap_closer", title="Gap closer", description="Plant a crop that fills a food gap.", icon="balance"),
    Achievement(id="full_cycle", title="Full cycle", description="Cook, check health and plant: the whole loop.", icon="cycle"),
]
BY_ID = {a.id: a for a in CATALOG}


class Progress(BaseModel):
    xp: int = 0
    meals_cooked: int = 0
    rescued: list[str] = Field(default_factory=list)
    planted: list[str] = Field(default_factory=list)
    checked_health: bool = False
    unlocked: list[str] = Field(default_factory=list)

    @property
    def level(self) -> int:
        return 1 + self.xp // XP_PER_LEVEL

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES[min(self.level, len(LEVEL_NAMES)) - 1]

    @property
    def level_pct(self) -> float:
        return (self.xp % XP_PER_LEVEL) / XP_PER_LEVEL * 100

    @property
    def cycle(self) -> list[bool]:
        """Cook, check health, plant: which steps of the loop are done."""
        return [self.meals_cooked > 0, self.checked_health, bool(self.planted)]


class Reward(BaseModel):
    """What one action earned, for the popup."""

    action: str
    xp_gained: int
    xp_before: int
    xp_after: int
    level_before: int
    level_after: int
    unlocked: list[Achievement]

    @property
    def leveled_up(self) -> bool:
        return self.level_after > self.level_before


class ProgressStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS progress (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL)")

    def load(self) -> Progress:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM progress WHERE id = 1").fetchone()
        return Progress.model_validate_json(row[0]) if row else Progress()

    def save(self, progress: Progress) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO progress (id, payload) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET payload = excluded.payload",
                (progress.model_dump_json(),),
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def _finish(store: ProgressStore, before: Progress, after: Progress, action: str, gained: int, new_ids: list[str]) -> Reward:
    if all(after.cycle) and "full_cycle" not in after.unlocked:
        new_ids.append("full_cycle")
        gained += 50
    after.xp = before.xp + gained
    after.unlocked = after.unlocked + [i for i in new_ids if i not in after.unlocked]
    store.save(after)
    return Reward(
        action=action,
        xp_gained=gained,
        xp_before=before.xp,
        xp_after=after.xp,
        level_before=before.level,
        level_after=after.level,
        unlocked=[BY_ID[i] for i in new_ids if i not in before.unlocked],
    )


def record_cook(
    store: ProgressStore, recipe: Recipe, risks_before: list[SpoilageRisk], risks_after: list[SpoilageRisk]
) -> Reward:
    """Cooking saves the main food; extra XP for a same-day rescue."""
    before = store.load()
    after = before.model_copy(deep=True)
    main = recipe.ingredients[0] if recipe.ingredients else None
    risk = next((r for r in risks_before if main and r.item_id == main.item_id), None)

    gained = 20
    new: list[str] = []
    after.meals_cooked += 1
    if main:
        after.rescued.append(main.name)
    if after.meals_cooked == 1:
        new.append("first_rescue")
    if risk is not None and risk.days_remaining <= 0:
        gained += 15
        new.append("last_minute")
    if after.meals_cooked >= 3:
        new.append("plan_complete")
    if not any(r.risk in ("critical", "high") for r in risks_after):
        gained += 25
        new.append("zero_waste")
    return _finish(store, before, after, f"Cooked {recipe.name.lower()}", gained, new)


def record_health_check(store: ProgressStore) -> Reward | None:
    before = store.load()
    if before.checked_health:
        return None
    after = before.model_copy(deep=True)
    after.checked_health = True
    return _finish(store, before, after, "Checked food health", 10, ["health_check"])


def record_plant(store: ProgressStore, crop: GrowCrop, gaps: list[str]) -> Reward:
    before = store.load()
    after = before.model_copy(deep=True)
    after.planted.append(crop.crop)
    gained = 20
    new: list[str] = []
    if len(after.planted) == 1:
        new.append("green_thumb")
    if crop.fills in gaps:
        gained += 10
        new.append("gap_closer")
    return _finish(store, before, after, f"Planted {crop.crop}", gained, new)
