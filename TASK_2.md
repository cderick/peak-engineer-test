# Task 2: Wearable history

Members' wearable data arrives as daily deliveries. Each member uses one
provider, and providers differ in field names, units and which metrics they
supply. Ingest and store those deliveries, then add 30 days of wearable history
to the home screen alongside the biomarkers.

## Requirements

- Implement persistence in `POST /api/users/{user_id}/wearables`.
- Model the data using the existing store API. Choose the document structure,
  partition keys and sort keys.
- Display a line chart for each metric below, with dates, values and units.
- Show the latest 30 calendar days, ending on the member's latest wearable date.
- Support the supplied data for all four members and keep their results separate.

| Metric | Daily value |
| --- | --- |
| Resting heart rate | Beats per minute |
| Steps | Total steps |
| Sleep efficiency | Percentage |

Deliveries are partial in places: a member can have days with no delivery, a
delivery can carry a null field, and a provider may not expose every metric in
the table. Some days are delivered twice; the later file carries a corrected
value and a distinct `upload_id`. Decide whether a repeated delivery for the same
day replaces, merges with or is rejected in favour of the earlier one, and how
missing values appear on the charts. Briefly document those decisions and your
storage layout. Keep the biomarker history from task 1 working.

## Import the deliveries

[app/routes/ingest.py](app/routes/ingest.py) contains the endpoint shell. It accepts
one day's envelope and currently returns `stored: false` without writing data.

Fixtures are in `data/wearables/{user_id}/`, with one JSON file per delivery and
up to 90 days of history. Repeated deliveries have an `_r2` suffix. With
`scripts/dev` running, replay a member's files:

```sh
scripts/ingest-wearable-data.py --user user-1
```

Repeat for `user-2`, `user-3` and `user-4`. The script posts files in filename
order. Each request contains the provider, member and a single day's `data`
object.

Ingest is unauthenticated for this exercise. Leave authentication unchanged.
Bootstrap clears imported data, so run it before importing wearables.

## Performance and verification

Serve the chart data through `GET /api/home`. After importing the fixtures, keep
that endpoint within the 35 ms p95 budget:

```sh
scripts/bench.py --email james.chen@example.com
```

Use the other members' emails to measure their responses too. The benchmark
requires a running server and exits with a non-zero status when it exceeds the
budget.

Follow the [README constraints](README.md#constraints).
[tests/test_wearables.py](tests/test_wearables.py) loads fixture files and signs
members in; its expected failure clears once ingest persists. Extend it with
tests for ingest and the daily history returned to the client.
