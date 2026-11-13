# Demo script

Use this with a fresh checkout and no API key. The spoilage numbers come from
the shelf-life table, which is the point of the fallback: the kitchen plan
still runs with the network unplugged.

## Before you start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest
streamlit run app.py
```

`pytest` should pass before you open the app. If a database is left over from
an earlier run, delete `data/fallow.db` so the sample inventory loads again.

Leave `LLM_API_KEY` empty and `SENSOR_MODE=mock`.

## 1. Dashboard

Open the home page.

You should see:

- Spinach is the first row. In the sample it expires on 13 November 2026, so
  on that day it is critical, and after that day it is the most overdue item.
  Chicken, carrots, bread, and milk follow. Rice and beans stay at the bottom.
- The caption under the table says the estimates come from the shelf-life table.
- The sidebar says `Sensor: mock` and `Spoilage: shelf-life table`.
- The first meal uses spinach and rice. Rice is the staple that can wait.
- The garden block says Hudson Valley, about 7 °C, moist loam, and frost.
- The balance line says planting covers the fresh-food gap. Kale, spinach,
  and garlic are the crops. Garlic is there because a cold, frosty reading
  does not support summer crops.

## 2. Inventory

Open **Inventory** in the sidebar.

- The sample rows are listed: spinach, chicken, carrots, milk, bread, rice, beans.
- The spoilage table matches the dashboard.
- Add a food. Name it `strawberries`, category `berries`, quantity `1`,
  unit `box`, and check that you know the expiry date. Set that date to
  tomorrow.
- The new row appears, and strawberries show up as high risk.
- Remove the strawberries row with **Remove**. The sample items stay.

## 3. Grow

Open **Grow**.

- Location, temperature, soil, and frost match the fixture.
- Open **Raw sensor reading** and confirm it is `fixtures/sensor.sample.json`
  (Hudson Valley, frost risk true, soil moisture 0.45).
- The planting table is the cold-season list: kale, spinach, garlic.

## 4. Live mode is a clear stop, not a fake forecast

Stop Streamlit. In `.env` set:

```
SENSOR_MODE=live
```

Start Streamlit again and open **Grow**.

You should see a warning that the live sensor feed is not built yet, and no
invented weather underneath it. Set `SENSOR_MODE` back to `mock` when you
are done.

## 5. Optional model call

Put a real key in `LLM_API_KEY`, restart Streamlit, and reload the dashboard.
Rows the model returns are marked `llm`. If the key is wrong, the request
fails, and the page falls back to the same shelf-life table as step 1.
