# Fallow

Fallow is a survival-grade kitchen and garden planner. It tracks what is in
your pantry, uses an LLM to predict what will spoil first, and builds a
cooking plan so nothing goes to waste. A pluggable sensor feed (location,
weather, soil condition) then drives a grow plan that tells you what you can
plant and how to balance your food supply for resilience. Nothing rots,
nothing is wasted, everything is planned.

An **LLM** is a language model you call over the network. Fallow asks it for
JSON, then checks that JSON against a fixed shape. A **heuristic** is the
offline backup: a shelf-life table plus the expiry date already on the item.
A **protocol** here is the small contract every sensor must follow — one
`read()` method that returns the same snapshot type.

The live sensor is not built yet. The mock sensor replays a saved reading so
the garden page works today.

## Setup

From this directory, with Python 3.11 or newer:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Leave `LLM_API_KEY` blank to stay on the shelf-life table. Set
`SENSOR_MODE=mock` (the default) or `SENSOR_MODE=live`.

## Launch

This is a local website. Streamlit is the web server: it turns `app.py` into
pages you open in a browser. You do not need a separate frontend.

From this directory, with the virtualenv activated:

```bash
streamlit run app.py
```

Streamlit prints a local address, usually `http://localhost:8501`. Open that
in a browser. There are five pages in the top bar (on a phone, behind the
menu button):

- **Dashboard**: what to cook first, food health, spoilage, and planting.
- **Pantry**: everything on hand; add and remove food.
- **Soil & farm**: the sensor reading and what to plant.
- **Health**: which food groups (fresh food, calorie staples, protein) the
  pantry holds past the next three days.
- **Food & recipes**: step-by-step meals from food on hand. **Mark as cooked**
  uses up the main food and one portion of the staple.

The dashboard also shows **Weather** (from the sensor, including air CO2 and
radiation when the station reports them) and **Health** (blood oxygen and
heart rate from `fixtures/body.sample.json` until a watch or oximeter is
connected; wellness info, not medical advice).

**Your cycle** turns the loop into a game: cooking, checking health and
planting earn XP and unlock achievements, each with an animated popup.
**Reset demo data** at the bottom of the dashboard restores the sample pantry
and clears progress, for rehearsing the pitch.

The look (lavender backdrop, white cards, lime accents) lives in
`.streamlit/config.toml` and `fallow_ui.py`. The Plus Jakarta Sans font is
served from `static/fonts/`, so the app looks the same with no internet. After editing `fallow_ui.py`, stop the server with Ctrl+C and
start it again so Streamlit picks up the new styles.

Leave this command running while you use the site. Stop it with Ctrl+C in
that terminal. Nothing here is deployed to the public internet; it runs on
your machine.

The inventory is a SQLite file at `data/fallow.db`. The first launch copies
in `fixtures/inventory.sample.json`. Delete that database file to load the
sample again.

## Web demo, 3D watch and hardware

These run without Python. Open them in a browser (they need internet for
fonts, and the 3D page also loads Three.js from a CDN).

- `web/demo/index.html`: clickable demo of the whole app. Phone, Watch and
  Website views, a sensor simulator, cooking, planting and achievements.
- `web/watch3d/index.html`: 3D exploded view of the survival watch built from
  the CAD files. Explode slider, turn and flip controls, labels, and a live
  health screen on the watch face.
- `hardware/cad/`: the Onshape STEP files (Assembly 1).
- `hardware/fallow-watch.glb`: the same assembly as one GLB, one named node
  per part, for Blender or Three.js.
- `assets/logo/`: the Fallow logo as SVG (dark, lime, app tiles) and a 512 px PNG.

## Tests

```bash
pytest
```

`tests/test_spoilage_fallback.py` checks that a failed model call still
returns shelf-life risks. `tests/test_planner_inventory_only.py` checks that
every meal uses food already in the inventory.

## Layout

```
├── README.md
├── web/demo/index.html          # Clickable demo (no Python needed)
├── web/watch3d/index.html       # 3D exploded watch view
├── hardware/                    # STEP files, GLB, renders
├── assets/logo/                 # Logo SVG + PNG
├── pyproject.toml
├── .env.example                 # LLM_API_KEY, SENSOR_MODE=mock|live
├── app.py                       # Streamlit entry: theme + top navigation
├── fallow_ui.py                 # Shared styles and card components
├── .streamlit/config.toml       # Theme, colors, font files
├── static/fonts/                # Plus Jakarta Sans (SIL Open Font License)
├── views/
│   ├── dashboard.py
│   ├── pantry.py                # Was pages/1_Inventory.py
│   ├── farm.py                  # Was pages/2_Grow.py
│   ├── health.py
│   └── recipes.py
├── larder/
│   ├── models.py                # Pydantic: InventoryItem, SpoilageRisk, MealPlan, GrowPlan
│   ├── spoilage/
│   │   ├── predictor.py         # LLM call + heuristic fallback
│   │   └── shelf_life.py        # Static baseline table
│   ├── meals/
│   │   ├── planner.py
│   │   └── recipes.py           # Steps per meal; cooking reduces quantity
│   ├── health/nutrition.py      # Food-group reserve report
│   ├── health/vitals.py         # Body readings + reference-range labels
│   ├── achievements.py          # XP, levels, achievements (SQLite)
│   ├── grow/
│   │   ├── advisor.py
│   │   └── balance.py
│   ├── sensors/
│   │   ├── base.py              # SensorSnapshot model + Sensor protocol
│   │   ├── mock.py
│   │   └── live.py              # Built last
│   ├── llm/
│   │   ├── client.py            # Retries, timeout, JSON validation
│   │   └── prompts.py
│   └── store.py                 # SQLite
├── fixtures/
│   ├── inventory.sample.json
│   └── sensor.sample.json
├── tests/
│   ├── test_spoilage_fallback.py
│   └── test_planner_inventory_only.py
└── docs/
    ├── architecture.md
    └── demo-script.md
```

Each package under `larder/` also has an `__init__.py` so Python can import it.

## Known issues

The basic path works offline: sample pantry, shelf-life spoilage, a three-day
cook list, and a mock garden plan. Rough edges are written down in
[docs/known-issues.md](docs/known-issues.md) instead of being patched in this
baseline. The live sensor is one of those: it fails clearly until a real feed
exists.

## License

Apache License 2.0. See `LICENSE`.
