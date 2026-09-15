# Peak member dashboard

A small app that shows a member their bloodwork. Sign in, see every biomarker with
its latest value and which band that value falls into.

This is the codebase you will be working in. It runs, it has tests, and
real data to work with.

## The assessment

This task assesses your ability to work in an unfamiliar codebase and make sound
product and data decisions under a real constraint, using modern development
practices including proficient use of AI coding agents.

| Phase | Duration | Format | Focus |
| --- | --- | --- | --- |
| Phase 1: Independent development | 1 hour | Take home | Feature implementation, data modelling, product judgement, AI tool usage |
| *Submission* | | Git repository | Repository link shared with the Peak team at the end of the hour |
| Phase 2: Presentation & live coding | 1 hour | Paired session with a Peak engineer | Solution walkthrough, code walkthrough, live coding extension |

Both phases happen on the same day. **Remember to share your submission at the end
of Phase 1.**

There are two tasks: [Task 1](TASK_1.md) and [Task 2](TASK_2.md). Read both before
you start — task 2 changes what a sensible task 1 looks like. Work through both and
get as far as you can in the hour. As a rough guide, task 1 should take around 20
minutes, leaving the rest for task 2.

Not everyone finishes, and that is expected. Wherever you stop is where Phase 2
picks up, so leave what you have in a coherent state rather than leaving several
things half-wired, and note what you did not get to. We would rather see three
things that work and a clear account of the fourth than four things that do not.

## What we're looking for

- **Product behaviour** — readable charts, useful labels, values a member can
  inspect, sensible empty states.
- **Correctness** — member isolation, coherent date handling, API and UI agreeing.
- **Your understanding of the code** — feel free to use AI, but make sure you
  understand the outputs. We will be asking you to make changes.
- **Data modelling** — the store has no indexes or joins. What does your key layout
  make cheap to read, and what does it make expensive?
- **Product judgement** — the data has more in it than the tasks ask for, and some
  of it disagrees with itself. Use your judgement, and tell us what you decided.
- **Prioritisation** — how far you get, and whether what you got to actually works.
  Omissions you can name are fine; half-finished work you cannot account for is not.
- **AI tool usage** — be prepared to discuss how and where you used AI tools.

## Expected use of AI coding agents

You are **expected** to use AI coding agents (Claude Code, Cursor, Codex, etc.) in
your workflow.

- Be prepared to articulate **how** and **where** you used AI tools to help you.
- AI should accelerate development while maintaining high code quality.

## Submission

1. Push your work to a public Git repository.
2. Share the repository link with your interviewer at the end of the hour.
3. Include a `NOTES.md` at the repository root with:
   - Assumptions you made where the brief was ambiguous, and why you chose as you did.
   - Your storage layout, and what it makes cheap or expensive to read.
   - What you left out, and what you would do next.
   - How you used AI tools in your development process.

Bullets are fine and short is fine. This is where you get credit for decisions the
code alone cannot show.

## Tips

- **Start with the data.** Look at the seeded documents and the API responses before
  writing UI code. Understand the shapes and what is actually in them.
- **Read both tasks first.** The second one will change how you approach the first,
  and you will lose time if you have to rework task 1 to fit it.
- **Watch the store logs.** Every store call logs to the `scripts/dev` output, so you
  can see exactly which reads your code makes.
- **Don't vibe code the whole thing.** You will be making changes with us in Phase 2
  and will get stuck if you do not understand what you submitted.

## Run locally

Install [uv](https://docs.astral.sh/uv/); it installs Python 3.14 if missing. Then run
from the repository root:

```sh
scripts/bootstrap.py
scripts/dev
```

Open http://localhost:8000.

Bootstrap loads members, biomarker definitions and blood draws into `dev.db` from
the JSON files in `data/`.

The database includes these members. Sign in with their email; no password is required.

| Member ID | Name | Email |
| --- | --- | --- |
| user-1 | James Chen | james.chen@example.com |
| user-2 | Priya Raman | priya.raman@example.com |
| user-3 | Tom Okafor | tom.okafor@example.com |
| user-4 | Sofia Marek | sofia.marek@example.com |

API routes are in [app/routes/](app/routes/); request and response schemas are
available at http://localhost:8000/docs. API fields use snake_case, and successful
responses use `{"data": ..., "meta": ...}`.

## Development commands

Executable tasks are in `scripts/`. Run `ls scripts/` to list them.

| Command | Purpose |
| --- | --- |
| `scripts/bootstrap.py` | Clear `dev.db` and load the seed data |
| `scripts/test` | Run all tests |
| `scripts/lint` | Check lint, formatting and types |
| `scripts/fmt` | Apply lint fixes and formatting |
| `scripts/bench.py` | Benchmark home requests over HTTP; requires a running server |

`scripts/bench.py` measures HTTP latency against the running app, including network
time. Results depend on hardware and load.

## Client app

FastAPI serves the page at `/` and its assets under `/static/`. The client uses
plain JavaScript and DOM APIs, with no framework or build step. Edit the files in
[app/static/](app/static/) and reload the browser.

| File | Contents |
| --- | --- |
| [index.html](app/static/index.html) | Sign-in form, dashboard containers and script loading |
| [app.js](app/static/app.js) | API requests, sign-in state and biomarker rendering |
| [styles.css](app/static/styles.css) | Layout, colours and reference-range scales |
| [perf.js](app/static/perf.js) | Request timing panel and Chart.js example |

On load, `app.js` calls `GET /api/me` to check the session. After sign-in or session
restore, it fetches `GET /api/home` and renders `data.results`, grouped by category.
Each marker displays its value, status and reference ranges. The browser sends
the session cookie with API requests to the same origin.

Chart.js loads from a CDN before the application scripts and exposes the global
`Chart` constructor. `perf.js` uses it to plot recent request timings. Loading the
library requires internet access.

The timing panel tracks API requests through a `fetch` wrapper. It reports elapsed
time to response headers and server timings from `X-Response-Time-Ms`; it does not
measure JSON parsing or rendering. Use `scripts/bench.py` for the latency budget.

## Data model

- [data/members.json](data/members.json): member profiles.
- [data/biomarkers.json](data/biomarkers.json): supported biomarkers, units and reference ranges.
- [data/biomarkers/](data/biomarkers/): blood draws, grouped by member.

Documents live in a partitioned store backed by `dev.db`. A partition key groups
documents; a sort key identifies a document within that partition. Keys are
strings, ordered lexicographically. The store does not enforce document schemas.

The starting layout uses models from [app/models.py](app/models.py):

| Partition key | Sort key | Model and contents |
| --- | --- | --- |
| `user` | Member ID | `Member`: profile |
| `email` | Email address | `EmailPointer`: member ID for login lookup |
| `biomarker` | Biomarker ID | `BiomarkerDefinition`: name, unit, direction and reference ranges |
| `results:{user_id}` | ISO draw timestamp | `ResultsDocument`: member ID, timestamp and result list |

Each result stores its biomarker ID, value, unit, status, reference ranges and
optional source. Status and ranges are recorded as known at the time of the draw,
so the same biomarker can carry different ranges across a member's history and
may differ from the current `BiomarkerDefinition`. A draw can contain a partial
panel: a biomarker may be absent from any given draw.

## Storage API

Use [Store](app/store.py) for persistence. There are no field queries, joins or
secondary indexes.

| Method | Behaviour |
| --- | --- |
| `get(pk, sk, model=None)` | Return one document, or `None` |
| `query(pk, model=None, *, start=None, end=None)` | Yield `(sk, document)` from one partition in sort-key order |
| `keys(pk, *, start=None, end=None)` | Yield sorted keys without decoding documents |
| `scan(pk_prefix="", model=None)` | Yield `(pk, sk, document)` across matching partitions, ordered by both keys |
| `put(pk, sk, value)` | Insert or replace an entire document |
| `put_many(items)` | Write `(pk, sk, value)` tuples in one transaction; return the count |
| `delete(pk, sk)` | Delete one document; missing keys are ignored |
| `close()` | Release the connection |

Range bounds are start-inclusive and end-exclusive. An empty scan prefix matches
all partitions. Reads are lazy except `get`; scanning more documents means more
decoding work.

Every store call logs at INFO, so `scripts/dev` shows you the reads your code
actually makes. That log is the fastest way to see an access pattern you did not
intend.

Pass a Pydantic model to validate and return model instances. Omit it for
dictionaries. Writes accept either models or dictionaries. Route handlers obtain
a store through `Depends(get_store)`, which closes it after the request.

See [tests/test_store_api.py](tests/test_store_api.py) for examples.

## Constraints

- Preserve the store's public API. Use it for application persistence; do not
  bypass it with SQL or add another database. Store internals may change.
  Do not edit `tests/test_store_api.py`.
- Keep `/api/home` at or under 35 ms p95, the budget
  [scripts/bench.py](scripts/bench.py) enforces. The number is calibrated for a
  recent laptop with the server on localhost, so no network round trips are
  involved.
- Leave the deliberately simplified authentication in [app/auth.py](app/auth.py)
  unchanged.

Document layouts, application logic and the client may change within these
constraints.

## Import data

`scripts/bootstrap.py` validates the JSON with the application models and writes
through the store API. It also creates email lookups for the members. Draws retain
their stored ranges and statuses.

Bootstrap validates the fixtures, clears all existing documents, and loads the
seed data. This removes imported wearable data and additional draws. It logs the
number of documents cleared and loaded.

### Biomarker draws

JSON copies of the seeded draws are in `data/biomarkers/{user_id}/`.
To import a draw, send `tested_at` and a non-empty `results` list to
`POST /api/users/{user_id}/biomarkers/draws`:

```sh
curl http://localhost:8000/api/users/user-1/biomarkers/draws \
  -H 'Content-Type: application/json' \
  --data '{"tested_at":"2026-09-05T08:30:00","results":[{"biomarker_id":"hs_crp","value":0.6,"unit":"mg/L"}]}'
```

Ingest does not require sign-in for this exercise. Production endpoints must
authenticate the sender and authorize writes to the requested member.

The API rejects the entire draw if a biomarker is unknown or its unit differs
from the definition. Reposting a timestamp merges results by biomarker ID and
preserves omitted markers. Status and ranges come from current definitions;
importing does not restore historical classifications from the JSON.
