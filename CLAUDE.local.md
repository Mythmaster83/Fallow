# Fallow — CLAUDE.md

## What This Is

Fallow is a survival-grade kitchen and garden planner being built at HackPerimeter hackathon. It extends a food inventory state machine to cover the full biological cycle: from seed/animal through growing, harvest, raw, cooked, consumed, and back to compost/soil amendment. Environmental sensors (soil, weather, location) drive grow and foraging recommendations.

The hackathon theme is **survival**. The pitch: nothing rots, nothing is wasted, everything is planned — from dirt to plate and back.

## Stack

- **Python 3.11+**, no type: ignore hacks — use proper types
- **Streamlit** for UI (app.py + pages/)
- **Pydantic** for all data models (larder/models.py is the shared language)
- **SQLite** via larder/store.py for inventory persistence
- **LLM** (OpenAI-compatible API) for spoilage prediction, with heuristic fallback
- **pytest** for tests

## Architecture

```
Streamlit pages → plain Python functions (no Streamlit imports in larder/)
                → SQLite inventory
                → Spoilage predictor (LLM + shelf-life table fallback)
                → Meal planner (deterministic, inventory-only)
                → Sensor protocol (mock fixture / live stub)
                → Grow advisor (rule-based from sensor snapshot)
```

Key principle: **larder/ never imports streamlit.** Pages call larder functions. Tests call the same functions with no browser.

## Project Layout

- `app.py` — Streamlit dashboard entry point
- `pages/` — Streamlit sub-pages (Inventory, Grow)
- `larder/models.py` — ALL Pydantic models live here. This is the source of truth for data shapes.
- `larder/spoilage/` — predictor.py (LLM + fallback), shelf_life.py (static table)
- `larder/meals/planner.py` — deterministic meal planning from inventory
- `larder/grow/` — advisor.py (rule-based planting), balance.py (pantry gap analysis)
- `larder/sensors/` — base.py (protocol + SensorSnapshot), mock.py, live.py (stub)
- `larder/llm/` — client.py (retries, timeout, JSON validation), prompts.py
- `larder/store.py` — SQLite, one row per item as JSON
- `fixtures/` — sample inventory and sensor data
- `tests/` — pytest, no Streamlit dependency
- `docs/` — architecture.md, demo-script.md, known-issues.md

## The State Machine

Food moves through lifecycle states. The extended survival model:

```
seed → growing → harvest → raw → opened → cooked → consumed/trashed
                                                          ↓
                              compost ← scraps ←──────────┘
                                 ↓
                             soil amendment → (back to seed)
```

Storage transitions (fridge ↔ freezer ↔ pantry ↔ counter ↔ root cellar ↔ ground) are independent of lifecycle state. Every transition recalculates expiry/spoilage.

## Conventions

- **Models first.** Any new data shape goes in larder/models.py as a Pydantic model before being used anywhere.
- **No Streamlit in larder/.** If a function needs to be tested, it belongs in larder/, not in pages/.
- **Heuristic fallback always.** Any LLM-powered feature must have a deterministic offline fallback. The app works with LLM_API_KEY unset.
- **Sensor protocol.** New sensor types implement `read() -> SensorSnapshot`. Mock reads from fixtures/, live reads from hardware/API.
- **Inventory is sacred.** The meal planner never invents food. It only uses items already in the inventory. Same for spoilage — unknown IDs are dropped.
- **JSON in, Pydantic validates.** Fixtures, DB rows, and LLM responses all go through Pydantic validation.

## Testing

```bash
pytest
```

Tests must run without Streamlit, without an LLM key, and without network. They call larder/ functions directly. If you add a feature to larder/, add a test.

## What NOT To Do

- Don't add calorie counting, macro tracking, or diet features. This is logistics, not nutrition.
- Don't make the UI moralistic about food choices. Tone is practical/survival, not wellness.
- Don't import streamlit inside larder/ packages.
- Don't assume the LLM is available. Every code path must work offline.
- Don't invent inventory items in meal plans or grow plans. Only reference what exists.
- Don't add heavyweight dependencies without checking — this needs to run on hackathon laptops.

## Hackathon Context

- **Time left: ~6 hours** including pitch prep
- **Pitch: 1 minute 30 seconds** — embedded demo video, not live demo
- **Presentation: reveal.js** (single HTML file, Claude Code can edit directly)
- **Priority: working demo flow > polish > edge cases**
- **Team: multiple people working in parallel**

## Demo Flow (what needs to work end-to-end)

1. Show inventory with spoilage urgency ranking
2. Show meal plan generated from expiring items
3. Show sensor data → grow recommendations
4. Show the full cycle: harvest → inventory → cook → compost → soil → grow

## Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
streamlit run app.py
```

`SENSOR_MODE=mock` (default) uses fixtures. `LLM_API_KEY` blank uses shelf-life heuristics.
