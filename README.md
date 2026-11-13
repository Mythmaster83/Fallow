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

The live sensor reads weather, frost, and soil moisture from Open-Meteo. The
mock sensor replays a saved reading so the garden page works offline.

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
in a browser. The top bar has Dashboard, Pantry, Soil & farm, Health,
Food & recipes, and Cycle.

Leave this command running while you use the site. Stop it with Ctrl+C in
that terminal.

The inventory is a SQLite file at `data/fallow.db`. The first launch copies
in `fixtures/inventory.sample.json`. Delete that database file to load the
sample again.

## Deploy

A push to `main` publishes the app to Cloudflare Workers. The workflow is
`.github/workflows/cloudflare.yml`. It needs the Workers Paid plan, because
Streamlit cannot start inside the free plan's CPU limit, and these GitHub
Actions secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

The public site starts from the sample inventory. Pantry edits live on that
Worker and reset after the instance goes idle.

## Tests

```bash
pytest
```

`tests/test_spoilage_fallback.py` checks that a failed model call still
returns shelf-life risks. `tests/test_planner_inventory_only.py` checks that
every meal uses food already in the inventory. `tests/test_recipes_and_health.py`
checks the recipe steps and the food-group grades the new screens show.

## Layout

```
├── README.md
├── pyproject.toml
├── .env.example                 # LLM_API_KEY, SENSOR_MODE=mock|live
├── app.py                       # Streamlit entry and top navigation
├── fallow_ui.py                 # Shared look for every screen
├── views/
│   ├── dashboard.py
│   ├── pantry.py
│   ├── farm.py
│   ├── health.py
│   └── recipes.py
├── static/fonts/                # Plus Jakarta Sans, served with the app
├── larder/
│   ├── models.py                # Pydantic: InventoryItem, SpoilageRisk, MealPlan, GrowPlan
│   ├── spoilage/
│   │   ├── predictor.py         # LLM call + heuristic fallback
│   │   └── shelf_life.py        # Static baseline table
│   ├── meals/
│   │   ├── planner.py
│   │   └── recipes.py           # Steps and "mark cooked" amounts
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
│   ├── health/nutrition.py      # Fresh, staple, and protein reserves
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
baseline.

## License

Apache License 2.0. See `LICENSE`.
