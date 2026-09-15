# Task 1: Biomarker history

The home screen shows a member's latest blood results. Add charts so they can see
how each biomarker has changed over time and how its values relate to the
reference ranges.

## Requirements

- Keep the latest value and unit visible for each biomarker.
- Show its available history in chronological order, with dates and values that
  the member can inspect.
- Display reference ranges alongside the history.
- Use the signed-in member's results.

Choose the layout and interaction. The history should be accessible from the
home screen; a table alone is not sufficient.

## Existing data and code

Bootstrap loads the blood draws into `results:{user_id}`, keyed by draw timestamp.
JSON copies are in [data/biomarkers/](data/biomarkers/), and the models are in
[app/models.py](app/models.py). This task does not require new ingest code.

The client fetches `GET /api/home`. You can extend that response or add an
endpoint. [Chart.js](https://www.chartjs.org/) is available in the client; the
performance monitor in [app/static/perf.js](app/static/perf.js) includes an example.

Follow the [README constraints](README.md#constraints). Add tests for the history
behaviour and briefly document any assumptions about displaying values and ranges.
