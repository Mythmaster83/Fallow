# Known issues

These are real gaps in the baseline. They are listed here so the next change
can pick them up one at a time. None of them block the offline demo: sample
pantry, shelf-life spoilage, a short cook list, and the mock garden plan.

## Spoilage

- A model answer is kept even when it disagrees with a known expiry date. If
  the model says the chicken has 20 days and the label says tomorrow, the
  dashboard shows 20. Later: when `expires_on` is set, do not let the model
  move the date.
- A failed model call looks the same as a missing API key. Both show the
  shelf-life caption. Later: show one line that the call failed.
- The client always sends `response_format: json_object`. A server that
  rejects that field returns HTTP 400, and that status is not retried, so a
  valid key on a stricter compatible API never produces a model estimate.
- The client also retries a JSON body that fails schema checks. A model that
  keeps returning the wrong shape spends the whole retry budget.

## Meals

- Every urgent meal is paired with the same calmest staple. Three meals can
  all list rice, and the plan never checks whether the quantity covers that.
- Bread and other staple categories can still get their own meal, and that
  meal also attaches rice. A loaf does not need a second grain beside it.
- The cook list is capped at `horizon_days` (3 on the dashboard). Extra urgent
  items stay in `priority_item_ids` and on the spoilage table, but the summary
  does not say they did not fit.
- Recipe steps are fixed templates per food category, and a staple portion is
  a rough per-unit guess (a quarter kilo of rice, one can of beans).
- There is no edit form. You can add or remove a row, not change the expiry
  on an existing one.

## Pantry data

- The sample dates are fixed in November 2026. On that day spinach is critical.
  On a later day the same rows are overdue by a growing number of days. Later:
  seed the sample relative to today.
- Shelf life ignores where the food sits. Freezer and counter use the same
  table unless you pick the `frozen` category yourself.
- Two rows can share a display name. Meals key off ids, so the plan is still
  honest, but the table looks like one food twice.

## Garden and sensors

- The live feed is not built. `SENSOR_MODE=live` raises
  `LiveSensorUnavailable` on purpose.
- Season comes from the fixture timestamp, while spoilage uses today's date.
  The garden can still say "frost, plant kale" when the pantry math is for a
  different day. The raw reading has `captured_at`; the metrics do not show it.
- A winter month forces the cold crop list even if that reading is warm and
  frost-free. `cold` is true when the month is November–March, and the warm
  list only runs in May–September.
- Dry soil only drops spinach. Other thirsty crops stay.
- Protein-from-the-pantry is a short name list (`beans`, `lentils`, `tofu`,
  `chickpeas`). `soybeans` does not match. `green beans` does, and then counts
  as stored protein and calories, which can hide a real gap.
- A fixture that fails validation (missing field, bad type) is not caught by
  the pages. They catch file and mode errors, not a Pydantic validation
  error, so a broken fixture becomes a traceback instead of the warning used
  for the live sensor.
