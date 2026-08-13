# Rebuttal

Insurance denial appeals that remember — every appeal filed makes the next one
smarter, for you and for everyone else. Built in one afternoon at the MongoDB
Persistent Context Sprint (Pier 48, San Francisco, August 13, 2026).

## Why "No Cold Start"

The stored state is outcomes, not reference text. `attempts` records every
strategy this user has deployed and how it landed; the core aggregation
**excludes strategies the user already lost with** before ranking. The same
denial letter returns different rankings — and a differently-argued draft —
after a recorded loss. Recorded outcomes also update per-strategy rolling
stats, so every filed appeal sharpens the ranking for the next patient.

## How it works

One aggregation on `denial_profiles`:

```
$vectorSearch (Atlas Vector Search automated embeddings, voyage-4, raw-text query)
  → $match excluding this user's failed strategies   <- the memory
  → $facet: per-strategy overturn rates + sample sizes
            (with $lookup provenance from raw imr_decisions),
            evidence frequency among overturned neighbors,
            overall stats
```

- **Corpus:** 35K+ real California IMR determinations loaded verbatim
  (`ingest.py`); a Fireworks-powered classification pass (`extract.py`) turns
  findings narratives into searchable `denial_profiles` against a frozen
  closed taxonomy (`taxonomy.py`) — no free-invented strategy labels.
- **Drafting:** OpenRouter writes the appeal letter around the single top
  non-excluded strategy, with the user's already-failed strategies passed as
  "DO NOT USE"; a deterministic composer takes over automatically if the LLM
  call fails.
- **Search resilience:** `SEARCH_MODE=lexical` swaps the vector stage for an
  Atlas Search text stage — the demo survives either way.
- **UI:** one plain HTML page served by FastAPI. No dashboard, no charts.

Run:

```bash
pip install -r requirements.txt
cp .env.example .env   # add the Atlas connection string + API keys
python ingest.py && python seed_taxonomy.py && python seed_catalogs.py
python create_index.py
python extract.py      # optional: real-data classification pass (Fireworks)
uvicorn main:app --port 8000
python test_exclusion.py   # acceptance: same letter, different ranking after a loss
```

## Data credit (noncommercial)

Source data is **Independent Medical Review (IMR) Determinations, Trend** from
the California Department of Managed Health Care (DMHC), published on the CHHS
Open Data Portal, with credit also to the Office of the Patient Advocate.

Collection `imr_decisions` stores source rows **verbatim and unmodified**.
Derived collections (`denial_profiles`, `strategies`, `evidence_types`)
reference source rows by `ReferenceID` and do not alter the public dataset.

Noncommercial use of the unmodified source data. See CHHS / DMHC terms of use.

Dataset: https://data.chhs.ca.gov/dataset/independent-medical-review-imr-determinations-trend

## What was built during the event vs. what is public data

- **Built today (all code in this repo):** everything — see commit timestamps.
- **Public data (not ours, unmodified):** the DMHC IMR rows in `imr_decisions`.

## Not legal or medical advice

Rebuttal reports outcome statistics from public regulatory records and drafts
correspondence. It does not represent anyone.

## Team

Sasha — corpus, taxonomy & extraction · Jose Cruz — ranking pipeline, exclusion memory, UI, demo
