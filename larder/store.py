"""SQLite inventory.

Each item is stored as one JSON payload so the table does not drift from
``InventoryItem``. Connections are opened per call, which keeps Streamlit's
reruns from tripping SQLite's same-thread check.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from larder import project_root
from larder.models import CycleEvent, InventoryItem, Transition


def default_db_path() -> Path:
    """``FALLOW_DB_PATH`` overrides the location (used for clean screenshots)."""
    override = os.environ.get("FALLOW_DB_PATH", "").strip()
    if override:
        return Path(override)
    return project_root() / "data" / "fallow.db"


def default_inventory_fixture() -> Path:
    return project_root() / "fixtures" / "inventory.sample.json"


def open_store(path: Path | None = None) -> InventoryStore:
    """Open the database, and load the sample inventory the first time."""
    db_path = Path(path) if path is not None else default_db_path()
    fresh = not db_path.exists()
    store = InventoryStore(db_path)
    if fresh:
        try:
            store.seed_from_fixture(default_inventory_fixture())
        except Exception:
            db_path.unlink(missing_ok=True)
            raise
    return store


def load_inventory_fixture(path: Path) -> list[InventoryItem]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Inventory fixture must be a JSON list: {path}")
    return [InventoryItem.model_validate(row) for row in raw]


class InventoryStore:
    """Read and write inventory items."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS inventory (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL
                )
                """
            )

    def list_items(self) -> list[InventoryItem]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM inventory").fetchall()
        items = [InventoryItem.model_validate_json(row["payload"]) for row in rows]
        return sorted(items, key=lambda item: item.name.lower())

    def upsert(self, item: InventoryItem) -> None:
        payload = item.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO inventory (id, payload) VALUES (?, ?)
                ON CONFLICT(id) DO UPDATE SET payload = excluded.payload
                """,
                (item.id, payload),
            )

    def get(self, item_id: str) -> InventoryItem | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM inventory WHERE id = ?", (item_id,)).fetchone()
        return None if row is None else InventoryItem.model_validate_json(row["payload"])

    def save(self, transition: Transition) -> None:
        """Persist a lifecycle step: upsert its items, append its events."""
        for item in transition.items:
            self.upsert(item)
        with self._connect() as conn:
            conn.executemany(
                "INSERT INTO events (payload) VALUES (?)",
                [(event.model_dump_json(),) for event in transition.events],
            )

    def list_events(self, limit: int = 50) -> list[CycleEvent]:
        """Most recent first."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM events ORDER BY seq DESC LIMIT ?", (limit,)
            ).fetchall()
        return [CycleEvent.model_validate_json(row["payload"]) for row in rows]

    def delete(self, item_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM inventory WHERE id = ?", (item_id,))

    def reset(self, fixture: Path | None = None) -> list[InventoryItem]:
        """Wipe every item and the step history, then reload the sample."""
        with self._connect() as conn:
            conn.execute("DELETE FROM inventory")
            conn.execute("DELETE FROM events")
        return self.seed_from_fixture(fixture or default_inventory_fixture())

    def seed_from_fixture(self, path: Path) -> list[InventoryItem]:
        items = load_inventory_fixture(path)
        for item in items:
            self.upsert(item)
        return items

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn
