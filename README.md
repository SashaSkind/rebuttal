# Rebuttal

Insurance denial appeals that remember — every appeal filed makes the next one
smarter, for you and for everyone else. Built in one afternoon at the MongoDB
Persistent Context Sprint (Pier 48, San Francisco, August 13, 2026).

## Why "No Cold Start"

The stored state is outcomes, not reference text. `attempts` records every
strategy this user has deployed and how it landed; the core aggregation
EXCLUDES strategies the user already lost with before ranking. The same denial
letter returns different rankings — and a differently-argued draft — after a
recorded loss. Recorded outcomes also update per-strategy rolling stats, so
every filed appeal sharpens the ranking for the next patient.

## How it works

One aggregation on `denial_profiles`:
`$vectorSearch` (Atlas Vector Search automated embeddings, text query) →
`$match` excluding this user's failed strategies → `$facet` into per-strategy
overturn rates with `$lookup` provenance from raw `imr_decisions`, evidence
frequency among overturned neighbors, and overall stats. FastAPI + vanilla JS
on top. The appeal draft is composed deterministically from stored state: the
top non-excluded strategy, its live track record, the user's evidence list,
and the computed deadlines.

Run:

```bash
pip install -r requirements.txt
cp .env.example .env   # add the Atlas connection string
python fixtures.py && python create_index.py
uvicorn main:app --port 8000
python test_exclusion.py   # acceptance: same letter, different ranking after a loss
```

## What was built during the event vs. what is public data

- **Built today (all code in this repo):** `schema.py`, `main.py`, `fixtures.py`,
  `create_index.py`, `probe_search.py`, `test_exclusion.py`, `static/index.html`,
  and `ingest.py` — see commit timestamps.
- **Public data (not ours, unmodified):** California Independent Medical Review
  (IMR) Determinations, published by the California Department of Managed
  Health Care (DMHC) / Office of the Patient Advocate on the CHHS Open Data
  Portal. Raw rows are stored **verbatim and unmodified** in `imr_decisions`;
  everything derived (profiles, strategies, evidence scores) lives in separate
  collections referencing source rows by ID. Used noncommercially, with credit
  and thanks.

## Not legal or medical advice

Rebuttal reports outcome statistics from public regulatory records and drafts
correspondence. It does not represent anyone.

## Team

[Person A name] — corpus & extraction · [Person B name] — pipeline, exclusion, UI, demo
