# Notes

## Product and data decisions

- Each biomarker in `data.results` includes its chronological history. Its top-level
  value is that biomarker's latest available measurement, so a partial newer draw
  does not hide markers measured only in an earlier draw.
- Each history point uses the status and reference ranges stored with its own
  blood draw. The chart detail shows those ranges alongside each value.
- Wearable charts show 30 calendar dates ending on the latest imported wearable
  date. Missing deliveries and provider-null readings remain null, so Chart.js
  renders a gap rather than a zero.

## Wearable storage and ingest

- Normalized documents use `pk=wearables:{user_id}` and `sk=YYYY-MM-DD`.
  This makes a member's 30-day read a single bounded `Store.query`, and makes
  replacing one day a single `put`. Cross-member reporting would require scans
  and is intentionally not optimised.
- A repeat delivery fully replaces its normalized day. This avoids retaining a
  stale value when a corrected delivery omits or nulls a field.
- Oura, Garmin, and Fitbit provide resting BPM, interval step samples (summed to
  the daily total), and sleep efficiency percentage. Whoop provides resting BPM
  and sleep efficiency as a 0–1 fraction, which is converted to percent. Its
  energy series is in kJ and is not treated as steps, so Whoop `steps` is null.

## Verification and scope

- The browser UI has an expandable Chart.js biomarker chart per marker and three
  wearable charts. It intentionally keeps interaction minimal for live coding.
- `scripts/test` passes (54 tests), and `scripts/lint` passes. The supplied HTTP
  benchmark also passes for all four seeded members after importing their wearable
  fixtures; p95 was 1.9–3.3 ms against the 35 ms budget.

## AI usage

- Used Codex to inspect the repository and fixture variants, validate normalization
  rules, implement the focused changes, run verification, and review edge cases.
  Product semantics and storage trade-offs were decided explicitly before
  implementation.
