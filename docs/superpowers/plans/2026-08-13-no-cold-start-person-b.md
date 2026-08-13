# Rebuttal — Person B Implementation Plan (MongoDB "No Cold Start" Hackathon)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Event-day note:** This plan is a playbook executed DURING the hackathon (1:30–5:00 PM PT today). Code below is the answer key; the "Event prompt" block in each task is what you paste into your coding assistant at the event so the work is demonstrably built during event hours. Commit after every task — timestamped commits are your provenance evidence.

**Goal:** Build Person B's intelligence lane of *Rebuttal*: the vector-search → exclusion → ranking aggregation, the cases/attempts memory, the thin UI, the drafting call with fallback, and the demo — shippable by 4:15 PM.

**Architecture:** Single FastAPI service (`main.py`) over the Atlas sandbox cluster. One aggregation on `denial_profiles` does everything: `$vectorSearch` (auto-embedded text query) → exclusion `$match` against this user's failed `attempts` → `$facet` into (a) per-strategy overturn rates with `$lookup` provenance from raw `imr_decisions`, (b) evidence-frequency ranking, (c) overall stats. `attempts` is the memory that changes behavior. Optional LangGraph lifecycle with Atlas-persisted checkpoints on top.

**Tech Stack:** Python 3.11+, FastAPI + uvicorn, PyMongo, Atlas Vector Search (automated embeddings, `voyage-3-large`), Fireworks (OpenAI-compatible client) with OpenRouter fallback, LangSmith tracing, LangGraph + `langgraph-checkpoint-mongodb` (optional), plain HTML/JS UI.

**Spec:** `docs/superpowers/specs/2026-08-13-hackathon-brief.md`

## Global Constraints

- **Atlas Hackathon Sandbox cluster only** — from the organizers' emailed link. Never a personal cluster.
- **No Streamlit. No dashboard-as-main-feature. No charts.** UI is one page: paste box → ranked strategies → draft.
- Raw DMHC rows live in `imr_decisions` **verbatim and unmodified**; everything derived lives in separate collections referencing source rows by ID. Credit DMHC + Office of the Patient Advocate; state noncommercial use.
- Repo must be **public** by 4:50 PM; README states what was built today vs. what is public data.
- Only present work built during the event → generate/type code at the event via the prompts; commit frequently with real timestamps.
- `schema.py` is **frozen at 1:50 PM** (field names, collection names, slugs). Exception: `MIN_SAMPLE` is a tuning constant, not contract.
- File ownership: A owns `ingest.py`; B owns `main.py`, `fixtures.py`, `create_index.py`, `probe_search.py`, `test_exclusion.py`, `static/index.html`, `lifecycle.py`. Both import `schema.py`.
- Must-ship order: exclusion logic → real data with sample sizes → missing-evidence callout → video. Cut order: LangGraph → UI polish → extraction volume. **Never cut exclusion or the video.**
- Verification style: this plan uses acceptance scripts + curl checks instead of pytest TDD cycles — deliberate adaptation to the 3.5-hour clock. `test_exclusion.py` is the one real test and it is the spec's own acceptance test.

## Quick reference — the day at a glance

| Time | Task | Deliverable | Gate |
|---|---|---|---|
| before 1:00 | Task 0 | keys, accounts, tools ready | checklist done |
| 1:30–1:50 | Task 1 (joint) | `schema.py` frozen, fixtures inserted, vector index building, probe passes | `probe_search.py` prints scored hits |
| 1:50–2:40 | Task 2 | `/api/case` + `/api/case/{id}/analyze` return ranked strategies from fixtures | curl shows rates + sample sizes |
| 2:40–3:20 | Task 3 | draft records attempt; outcome recording; **exclusion works** | `test_exclusion.py` prints PASS |
| 3:15–3:30 | Task 4 (joint) | fixtures swapped for real corpus | `test_exclusion.py` PASSes on real data |
| 3:20–3:50 | Task 5 | UI + live LLM drafting with fallback | full demo loop in browser |
| 3:50–4:15 | Task 6 (optional) | LangGraph lifecycle checkpointed to Atlas | resume works; checkpoints visible in Atlas |
| 4:15–5:00 | Task 7 | video, README, public repo, submission | submitted with both names |

Run commands crib:

```bash
source .venv/bin/activate
uvicorn main:app --reload --port 8000        # the app
python fixtures.py                            # (re)seed fixtures
python create_index.py                        # create + poll vector index
python probe_search.py                        # is vector search alive?
python test_exclusion.py                      # THE acceptance test
```

---

### Task 0: Pre-event setup (do this morning — no project code)

**Files:** none in the event repo (rules: only present work built during the event). This is accounts, keys, and tooling.

**Interfaces:**
- Consumes: nothing.
- Produces: working API keys in a local note ready to paste into `.env` at 1:35; installed toolchain.

- [ ] **Step 1: Accounts and keys (~20 min)**
  - Fireworks: create account at fireworks.ai. The `MONGODB813` credit code likely redeems at the event — have the account ready; generate an API key now if the dashboard allows.
  - OpenRouter: create account, generate API key, load the $10 credit.
  - LangSmith: create free account at smith.langchain.com, generate API key.
  - GitHub: decide the event repo name (suggestion: `rebuttal`). **Create the repo at the event**, not before.

- [ ] **Step 2: Local toolchain (~10 min)**

```bash
python3 --version          # must be 3.11+
python3 -m pip install --upgrade pip virtualenv
# In Cursor: install MongoDB Agent Skills; have the MongoDB MCP Server config ready
# to point at the sandbox URI the moment the organizers' email arrives.
```

- [ ] **Step 3: Stage a local keys note (NOT in any repo)**

```
MONGODB_URI=            <- arrives via organizers' email at check-in
FIREWORKS_API_KEY=      <- from fireworks.ai
OPENROUTER_API_KEY=     <- from openrouter.ai
LANGSMITH_API_KEY=      <- from smith.langchain.com
```

- [ ] **Step 4: Print/open this plan and the spec on your machine.** You will paste the "Event prompt" blocks task by task.

---

### Task 1: Joint window — schema contract, fixtures, vector index (1:30–1:50)

**Files:**
- Create: `schema.py`, `fixtures.py`, `create_index.py`, `probe_search.py`, `demo/denial_letter.txt`, `requirements.txt`, `.env`, `.env.example`, `.gitignore`, `README.md` (stub)
- Test: `probe_search.py` (manual acceptance)

**Interfaces:**
- Consumes: sandbox `MONGODB_URI` from organizers' email.
- Produces (everything downstream depends on these exact names):
  - Collections: `imr_decisions`, `denial_profiles`, `strategies`, `evidence_types`, `cases`, `attempts`; DB name `nocoldstart`; vector index `profiles_vector` on `denial_profiles.search_text`.
  - `denial_profiles` doc shape: `{source_id: str, search_text: str, diagnosis_category: str, treatment_category: str, denial_type: str, outcome: "overturned"|"upheld", strategy_ids: [slug], evidence_present: [slug], is_fixture?: bool}`.
  - `strategies` doc: `{_id: slug, name, description, example_phrasing, stats: {attempts: int, overturns: int}}`.
  - `evidence_types` doc: `{_id: slug, name, description}`.
  - Python constants: `DB_NAME, IMR_DECISIONS, DENIAL_PROFILES, STRATEGIES, EVIDENCE_TYPES, CASES, ATTEMPTS, VECTOR_INDEX, RAW_REF_FIELD, RAW_DETERMINATION_FIELD, RAW_FINDINGS_FIELD, OUTCOME_OVERTURNED, OUTCOME_UPHELD, MIN_SAMPLE, STRATEGY_CATALOG, EVIDENCE_CATALOG`.

**The one strategic decision to sell to Person A in this window:** the strategy vocabulary is **closed** — the 8 slugs below live in `schema.py`, and A's extraction *classifies* findings into them instead of free-generating strategy names. This kills A's "generic mush" failure mode (spec calls it the demo-killer) and guarantees B's `$group` keys are dense and displayable. A's extraction prompt for this is in Appendix C — hand it over now.

- [ ] **Step 1: Repo scaffolding (2 min)**

```bash
mkdir rebuttal && cd rebuttal && git init
python3 -m venv .venv && source .venv/bin/activate
printf '.env\n.venv/\n__pycache__/\n' > .gitignore
```

`requirements.txt`:

```
fastapi
uvicorn
pymongo
python-dotenv
openai
requests
langsmith
langgraph
langgraph-checkpoint-mongodb
```

```bash
pip install -r requirements.txt
```

`.env.example` (copy to `.env` and fill):

```
MONGODB_URI=
FIREWORKS_API_KEY=
OPENROUTER_API_KEY=
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=rebuttal
# STUB_LLM=1   # uncomment to build/test before LLM keys are live
```

- [ ] **Step 2: Write `schema.py` — the frozen contract (propose this verbatim, argue ≤10 min)**

```python
"""Schema contract for Rebuttal. FROZEN AT 1:50 PM — nobody edits after that.
(Exception: MIN_SAMPLE is a tuning constant, not contract.)

Person A writes denial_profiles / strategies / evidence_types via ingest.py.
Person B reads them in main.py and owns cases / attempts.
imr_decisions holds raw DMHC rows VERBATIM — we never modify them; derived data
lives here in separate collections referencing source rows by ID (license terms).
"""

DB_NAME = "nocoldstart"

# ---- collection names ----
IMR_DECISIONS = "imr_decisions"      # raw DMHC rows, verbatim
DENIAL_PROFILES = "denial_profiles"  # derived; THE collection we vector-search
STRATEGIES = "strategies"            # argument archetype catalog + rolling stats
EVIDENCE_TYPES = "evidence_types"    # documentation category catalog
CASES = "cases"                      # live user state (B)
ATTEMPTS = "attempts"                # per-user strategy history (B) — the memory

VECTOR_INDEX = "profiles_vector"     # auto-embedding index on denial_profiles.search_text

# ---- raw-row field names (A confirms against the actual CSV header at 1:40;
#      if the header differs, fix THESE THREE LINES ONLY, before the freeze) ----
RAW_REF_FIELD = "ReferenceID"
RAW_DETERMINATION_FIELD = "Determination"   # e.g. "Overturned Decision of Health Plan"
RAW_FINDINGS_FIELD = "Findings"

# ---- normalized outcome values on denial_profiles.outcome ----
OUTCOME_OVERTURNED = "overturned"   # RAW determination startswith "Overturned"
OUTCOME_UPHELD = "upheld"

MIN_SAMPLE = 2   # min similar-case count for a strategy to rank; raise to 3 after real-data swap

# ---- denial_profiles document shape ----
# {
#   "_id": ObjectId,
#   "source_id": str,          # == imr_decisions[RAW_REF_FIELD] of the source row
#   "search_text": str,        # neutral 40–90 word summary of the DENIAL SITUATION.
#                              #   Auto-embedded by the vector index. MUST NOT mention
#                              #   the outcome (would bias retrieval).
#   "diagnosis_category": str, # e.g. "Cancer"
#   "treatment_category": str,
#   "denial_type": str,        # "Medical Necessity" | "Experimental/Investigational" | "Urgent Care"
#   "outcome": str,            # OUTCOME_OVERTURNED | OUTCOME_UPHELD (from raw Determination)
#   "strategy_ids": [str],     # 0–3 slugs from STRATEGY_CATALOG the reviewer's reasoning relied on
#   "evidence_present": [str], # slugs from EVIDENCE_CATALOG the findings credit
#   "is_fixture": bool,        # True only on hand-written fixtures; deleted at the 3:15 swap
# }
#
# cases:    {"_id", "created_at", "denial_text", "denial_date", "evidence_have": [slug],
#            "stage": "intake"|"drafted"|"responded"|"won", "deadlines": {
#              "internal_appeal_due": datetime, "external_review_due": datetime}}
# attempts: {"_id", "case_id": ObjectId, "strategy_id": slug, "stage": str,
#            "outcome": "pending"|"upheld"|"overturned", "recorded_at": datetime,
#            "letter": str}

# ---- CLOSED strategy vocabulary. A's extraction classifies into these slugs. ----
STRATEGY_CATALOG = [
    {"_id": "cite-clinical-guideline", "name": "Standard of care per named guideline",
     "description": "Establish the requested service is standard of care by citing a named clinical guideline (NCCN, ASCO, AAP, ACR...).",
     "example_phrasing": "NCCN Guidelines list the requested therapy as an appropriate treatment for this diagnosis.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "failed-alternatives", "name": "Plan-preferred alternative already failed",
     "description": "Document that the insurer's preferred alternative was tried and failed, or is contraindicated for this patient.",
     "example_phrasing": "The plan-preferred therapy was administered for 12 weeks and failed, as documented by the treating physician.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "peer-reviewed-evidence", "name": "Peer-reviewed literature support",
     "description": "Cite specific published studies demonstrating efficacy and safety of the requested service for this indication.",
     "example_phrasing": "Three peer-reviewed studies, including a randomized trial, support efficacy for this indication.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "treating-physician-rationale", "name": "Treating specialist's medical-necessity rationale",
     "description": "A detailed letter from the treating physician tying this patient's specific clinical facts to the requested service.",
     "example_phrasing": "My treating oncologist's attached letter details why this therapy is medically necessary for my specific presentation.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "plan-criteria-met", "name": "Plan's own criteria are met",
     "description": "Quote the insurer's published coverage criteria and show each element is satisfied or was misapplied.",
     "example_phrasing": "Under the plan's own medical policy, criteria 1 through 4 are met, as shown below.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "fda-approved-indication", "name": "FDA-approved / compendia-supported use",
     "description": "The service or drug is FDA-approved or listed in recognized compendia for exactly this indication.",
     "example_phrasing": "The requested drug is FDA-approved for this indication and cannot be deemed experimental.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "continuity-of-care", "name": "Interrupting effective treatment causes harm",
     "description": "An established treatment is working; interruption risks regression or deterioration.",
     "example_phrasing": "Discontinuing a therapy under which I have documentably improved would risk serious regression.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "urgent-risk", "name": "Delay poses imminent risk",
     "description": "Physician attests that delay poses imminent or irreversible harm, triggering expedited review.",
     "example_phrasing": "My physician attests that any delay in treatment poses an imminent threat to my health.",
     "stats": {"attempts": 0, "overturns": 0}},
]

EVIDENCE_CATALOG = [
    {"_id": "physician-letter", "name": "Letter of medical necessity",
     "description": "From the treating physician, tying patient specifics to the requested service."},
    {"_id": "clinical-guideline-citation", "name": "Named guideline excerpt",
     "description": "The relevant page of NCCN/ASCO/AAP/ACR or similar."},
    {"_id": "peer-reviewed-studies", "name": "Peer-reviewed studies",
     "description": "Published journal articles supporting the requested service."},
    {"_id": "prior-treatment-records", "name": "Prior treatment records",
     "description": "Records showing alternatives tried, duration, and outcomes."},
    {"_id": "imaging-test-results", "name": "Imaging / test results",
     "description": "Objective results supporting diagnosis and severity."},
    {"_id": "specialist-second-opinion", "name": "Specialist second opinion",
     "description": "Independent specialist concurrence with the treatment plan."},
    {"_id": "plan-policy-excerpt", "name": "Insurer's own policy excerpt",
     "description": "The plan's published coverage criteria for the service."},
    {"_id": "fda-compendia-support", "name": "FDA label / compendia listing",
     "description": "FDA approval or recognized compendium listing for this indication."},
]
```

- [ ] **Step 3: Write `demo/denial_letter.txt` (the demo input — fictional, labeled as such)**

```
[FICTIONAL SAMPLE — demo input only]
Meridian Health Plan of California
Date: July 20, 2026
Member: J. Rivera        Member ID: MHP-4821937
RE: Denial of Prior Authorization — Proton Beam Radiation Therapy

Dear Member,

We have reviewed the prior-authorization request submitted by your physician,
Dr. Osei, for proton beam radiation therapy for treatment of localized prostate
cancer. This request is DENIED.

Rationale: Proton beam radiation therapy is considered experimental and
investigational for this indication. Available clinical evidence does not
establish superiority over standard intensity-modulated radiation therapy
(IMRT), which is a covered benefit under your plan and is the medically
appropriate alternative.

You have the right to appeal this decision within 180 days of the date of this
letter. If the internal appeal upholds the denial, you may request an
Independent Medical Review through the California Department of Managed
Health Care.

Sincerely,
Utilization Management
Meridian Health Plan of California
```

- [ ] **Step 4: Write `fixtures.py` — catalogs + 20 fake profiles + 20 fake raw rows**

Format examples (first three; the Event prompt below generates the remaining 17 to the distribution spec):

```python
"""Seed fixture data so B can build the whole pipeline before A's extraction lands.
Idempotent: deletes previous fixtures first. Everything fixture-made carries
is_fixture=True so the 3:15 swap can delete it in one statement."""
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from schema import (ATTEMPTS, CASES, DB_NAME, DENIAL_PROFILES, EVIDENCE_CATALOG,
                    EVIDENCE_TYPES, IMR_DECISIONS, RAW_DETERMINATION_FIELD,
                    RAW_FINDINGS_FIELD, RAW_REF_FIELD, STRATEGIES, STRATEGY_CATALOG)

load_dotenv()
db = MongoClient(os.environ["MONGODB_URI"])[DB_NAME]

FIXTURE_PROFILES = [
    {"source_id": "FX-001",
     "search_text": ("Health plan denied proton beam radiation therapy for localized prostate "
                     "cancer as experimental and investigational, stating IMRT is the covered "
                     "alternative. The treating radiation oncologist recommends proton therapy "
                     "citing reduced rectal and bladder toxicity for this patient's anatomy, and "
                     "notes NCCN guidelines include it as an appropriate option."),
     "diagnosis_category": "Cancer", "treatment_category": "Cancer Care",
     "denial_type": "Experimental/Investigational", "outcome": "overturned",
     "strategy_ids": ["cite-clinical-guideline", "treating-physician-rationale"],
     "evidence_present": ["clinical-guideline-citation", "physician-letter"],
     "is_fixture": True},
    {"source_id": "FX-002",
     "search_text": ("Insurer denied continued proton beam therapy for prostate cancer, calling "
                     "it not medically necessary versus conventional radiation. Patient had "
                     "already begun a proton course; oncologist documented that switching "
                     "modalities mid-treatment risks overlapping toxicity and cited guideline "
                     "support for completing the planned course."),
     "diagnosis_category": "Cancer", "treatment_category": "Cancer Care",
     "denial_type": "Medical Necessity", "outcome": "overturned",
     "strategy_ids": ["cite-clinical-guideline", "continuity-of-care"],
     "evidence_present": ["clinical-guideline-citation", "prior-treatment-records"],
     "is_fixture": True},
    {"source_id": "FX-003",
     "search_text": ("Plan denied proton beam therapy for early-stage prostate cancer as "
                     "experimental, offering IMRT instead. The appeal cited general internet "
                     "articles about proton therapy without patient-specific clinical "
                     "documentation or guideline citations."),
     "diagnosis_category": "Cancer", "treatment_category": "Cancer Care",
     "denial_type": "Experimental/Investigational", "outcome": "upheld",
     "strategy_ids": ["peer-reviewed-evidence"],
     "evidence_present": [],
     "is_fixture": True},
    # ... FX-004..FX-020 generated at the event to the distribution spec ...
]

FIXTURE_RAW = [
    {RAW_REF_FIELD: "FX-001",
     RAW_DETERMINATION_FIELD: "Overturned Decision of Health Plan",
     RAW_FINDINGS_FIELD: ("The physician reviewer found that proton beam therapy is a clinically "
                          "appropriate option for this patient per NCCN guidelines, and that the "
                          "treating physician's rationale regarding toxicity was persuasive. The "
                          "health plan's denial was overturned."),
     "is_fixture": True},
    # ... one raw row per profile, FX-002..FX-020, determination matching outcome ...
]

def run():
    for coll in (DENIAL_PROFILES, IMR_DECISIONS):
        db[coll].delete_many({"is_fixture": True})
    for s in STRATEGY_CATALOG:
        db[STRATEGIES].replace_one({"_id": s["_id"]}, s, upsert=True)
    for e in EVIDENCE_CATALOG:
        db[EVIDENCE_TYPES].replace_one({"_id": e["_id"]}, e, upsert=True)
    db[DENIAL_PROFILES].insert_many(FIXTURE_PROFILES)
    db[IMR_DECISIONS].insert_many(FIXTURE_RAW)
    db[CASES].delete_many({})     # fresh demo state on reseed
    db[ATTEMPTS].delete_many({})
    print(f"profiles={db[DENIAL_PROFILES].count_documents({})} "
          f"raw={db[IMR_DECISIONS].count_documents({})} "
          f"strategies={db[STRATEGIES].count_documents({})} "
          f"evidence={db[EVIDENCE_TYPES].count_documents({})}")

if __name__ == "__main__":
    run()
```

**Fixture distribution spec (matters — it makes the demo deterministic):**

| Cluster | Profiles | Outcomes | Notes |
|---|---|---|---|
| Cancer / proton beam / experimental | 8 (FX-001..008) | 5 overturned, 3 upheld | Vocabulary must overlap `demo/denial_letter.txt`: proton beam, prostate cancer, experimental, IMRT, NCCN |
| Orthopedic / spinal surgery / medical necessity | 6 (FX-009..014) | 3 overturned, 3 upheld | |
| Autism / ABA therapy hours | 6 (FX-015..020) | 4 overturned, 2 upheld | |

Strategy stat targets across the 20 (each strategy appears on ≥2 profiles): `cite-clinical-guideline` ~7 uses / ~6 overturned (top rank); `failed-alternatives` ~5 / ~4 (clear #2 — beat two's replacement argument); `treating-physician-rationale` ~8 / ~5; `peer-reviewed-evidence` ~4 / ~2; others 2–3 uses each, mixed. Overturned cancer profiles should mostly include `clinical-guideline-citation` in `evidence_present` so the missing-evidence callout points there when the demo user checks only "physician-letter".

- [ ] **Step 5: Write `create_index.py` and run it (index builds while you start Task 2)**

```python
"""Create the automated-embedding vector index on denial_profiles.search_text and
poll until queryable. Safe to re-run."""
import os, time
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel
from schema import DB_NAME, DENIAL_PROFILES, VECTOR_INDEX

load_dotenv()
db = MongoClient(os.environ["MONGODB_URI"])[DB_NAME]

existing = [i["name"] for i in db[DENIAL_PROFILES].list_search_indexes()]
if VECTOR_INDEX not in existing:
    db[DENIAL_PROFILES].create_search_index(SearchIndexModel(
        name=VECTOR_INDEX, type="vectorSearch",
        definition={"fields": [
            {"type": "text", "path": "search_text", "model": "voyage-3-large"},
        ]},
    ))
    print("index creation requested…")
while True:
    info = list(db[DENIAL_PROFILES].list_search_indexes(VECTOR_INDEX))
    if info and info[0].get("queryable"):
        print("READY")
        break
    print("waiting for index build…")
    time.sleep(5)
```

If `create_search_index` rejects the automated-embedding definition (sandbox tier/API drift), create the same index in the Atlas UI: *Search & Vector Search → Create Index → Vector Search → automated embedding on `search_text`, model `voyage-3-large`*. If automated embeddings are unavailable entirely → **Appendix A** (manual embeddings, ~20 min).

- [ ] **Step 6: Write `probe_search.py` and run it — the go/no-go on auto-embedding**

```python
"""Go/no-go: does a raw-text $vectorSearch query work against the auto-embedded index?"""
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from schema import DB_NAME, DENIAL_PROFILES, VECTOR_INDEX

load_dotenv()
db = MongoClient(os.environ["MONGODB_URI"])[DB_NAME]
q = "proton beam therapy denied as experimental for prostate cancer"
try:
    hits = list(db[DENIAL_PROFILES].aggregate([
        {"$vectorSearch": {"index": VECTOR_INDEX, "path": "search_text",
                           "query": q, "exact": True, "limit": 5}},
        {"$project": {"_id": 0, "outcome": 1,
                      "score": {"$meta": "vectorSearchScore"},
                      "search_text": {"$substrCP": ["$search_text", 0, 80]}}},
    ]))
    for h in hits:
        print(round(h["score"], 3), h["outcome"], h["search_text"])
    print("OK — text-query vector search works" if hits
          else "No hits — index may still be building; re-run create_index.py")
except Exception as e:
    print(f"FAILED: {e}")
    print("If the error is about 'query'/'exact': try numCandidates:100 instead of exact.")
    print("If the error is about the index/model: switch to Appendix A (manual embeddings).")
```

Run: `python fixtures.py && python create_index.py && python probe_search.py`
Expected: cancer-cluster fixtures at the top with scores ~0.7+, `OK — text-query vector search works`.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: schema contract, fixtures, vector index, search probe

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

**Event prompt (paste to your assistant at 1:32, after `.env` is filled):**

> Set up the Rebuttal repo per my plan. Create `requirements.txt`, `.gitignore`, `.env.example`, `schema.py`, `demo/denial_letter.txt`, `create_index.py`, `probe_search.py` exactly as specified in my plan document (pasted below). Then write `fixtures.py`: it must upsert `STRATEGY_CATALOG` and `EVIDENCE_CATALOG` from `schema.py` into `strategies`/`evidence_types`, then insert 20 `denial_profiles` fixture docs (FX-001..FX-020) each paired with a matching `imr_decisions` raw row (`ReferenceID` == `source_id`, `Determination` = "Overturned Decision of Health Plan" or "Upheld Decision of Health Plan" matching the profile's `outcome`, `Findings` = 2–3 plausible reviewer sentences), all with `is_fixture: True`, idempotent (delete previous fixtures first), following this distribution: [paste the distribution table + stat targets]. `search_text` must be 40–90 words, a neutral summary of what was denied and why — never mentioning the outcome. The cancer cluster must share vocabulary with `demo/denial_letter.txt` (proton beam, prostate cancer, experimental, IMRT, NCCN). Then run `python fixtures.py && python create_index.py && python probe_search.py` and show me the output.

---

### Task 2: FastAPI + the ranking aggregation (1:50–2:40)

**Files:**
- Create: `main.py`
- Test: manual acceptance via `curl` + a 6-line Python check

**Interfaces:**
- Consumes: everything `schema.py` produces (Task 1); a queryable `profiles_vector` index.
- Produces (Tasks 3/5/6 rely on these exact signatures):
  - `client: MongoClient`, `db` — module-level.
  - `get_case(cid: str) -> dict` — raises 404 HTTPException if absent.
  - `rank_strategies(case: dict) -> dict` — returns `{"similar_cases": int, "overall_overturn_rate": float, "strategies": [{"strategy_id", "name", "description", "example_phrasing", "n", "overturns", "overturn_rate", "citations": [{"ref", "determination", "findings_excerpt"}]}], "missing_evidence": {"evidence_id", "name", "description", "seen_in_overturned", "overturned_total"} | None, "excluded_ids": [slug]}`.
  - `excluded_details(case_id: ObjectId) -> list[{"strategy_id", "name", "recorded_at"}]`.
  - `llm(messages: list) -> str`, `iso(d) -> str | None`, `utcnow() -> datetime`.
  - HTTP: `GET /` (UI), `GET /api/meta`, `POST /api/case` → `{"case_id", "deadlines"}`, `POST /api/case/{cid}/analyze` → rank_strategies result + `{"case_id", "excluded", "deadlines", "stage"}`.

- [ ] **Step 1: Write `main.py` — part 1: setup, models, helpers**

```python
"""Rebuttal — insurance denial appeals that remember. Person B's service.

Outcome data: California DMHC Independent Medical Review records (CHHS Open
Data Portal). Noncommercial use. Not legal or medical advice.
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from openai import OpenAI
from pydantic import BaseModel
from pymongo import MongoClient

from schema import (ATTEMPTS, CASES, DB_NAME, DENIAL_PROFILES, EVIDENCE_TYPES,
                    IMR_DECISIONS, MIN_SAMPLE, OUTCOME_OVERTURNED, OUTCOME_UPHELD,
                    RAW_DETERMINATION_FIELD, RAW_FINDINGS_FIELD, RAW_REF_FIELD,
                    STRATEGIES, VECTOR_INDEX)

load_dotenv()
client = MongoClient(os.environ["MONGODB_URI"])
db = client[DB_NAME]

try:  # LangSmith tracing — the promised two lines
    from langsmith.wrappers import wrap_openai
except ImportError:
    wrap_openai = lambda c: c

fireworks = wrap_openai(OpenAI(base_url="https://api.fireworks.ai/inference/v1",
                               api_key=os.environ.get("FIREWORKS_API_KEY", "x")))
openrouter = OpenAI(base_url="https://openrouter.ai/api/v1",
                    api_key=os.environ.get("OPENROUTER_API_KEY", "x"))
FW_MODEL = "accounts/fireworks/models/llama-v3p3-70b-instruct"  # verify in Fireworks model library at event
OR_MODEL = "openai/gpt-4o-mini"

app = FastAPI(title="Rebuttal")


class CaseIn(BaseModel):
    denial_text: str
    denial_date: Optional[str] = None     # "YYYY-MM-DD"
    evidence_have: list[str] = []


class OutcomeIn(BaseModel):
    outcome: str                          # "upheld" | "overturned"


def utcnow() -> datetime:
    return datetime.utcnow()


def iso(d):
    return d.strftime("%Y-%m-%d") if d else None


def get_case(cid: str) -> dict:
    case = db[CASES].find_one({"_id": ObjectId(cid)})
    if not case:
        raise HTTPException(404, "case not found")
    return case


def deadlines_for(denial_date: datetime) -> dict:
    internal = denial_date + timedelta(days=180)          # internal appeal window
    return {"internal_appeal_due": internal,
            "external_review_due": internal + timedelta(days=120)}  # then external review


def llm(messages: list) -> str:
    if os.environ.get("STUB_LLM"):
        return "[stub letter — unset STUB_LLM and set FIREWORKS_API_KEY for real drafting]"
    try:
        r = fireworks.chat.completions.create(model=FW_MODEL, messages=messages,
                                              temperature=0.4, max_tokens=1200)
        return r.choices[0].message.content
    except Exception as e:  # live-demo insurance: OpenRouter fallback
        print(f"fireworks failed ({e}); falling back to openrouter")
        r = openrouter.chat.completions.create(model=OR_MODEL, messages=messages,
                                               temperature=0.4, max_tokens=1200)
        return r.choices[0].message.content
```

- [ ] **Step 2: Write `main.py` — part 2: the core aggregation (THE product)**

```python
def rank_strategies(case: dict) -> dict:
    """$vectorSearch -> exclusion $match -> per-strategy stats + evidence + provenance.

    The $match on failed strategy_ids is what makes this memory, not search:
    the same denial letter ranks differently after a recorded loss.
    """
    failed = db[ATTEMPTS].distinct(
        "strategy_id", {"case_id": case["_id"], "outcome": OUTCOME_UPHELD})

    citations_map = {"$map": {
        "input": {"$slice": ["$source_rows", 3]}, "as": "r",
        "in": {"ref": f"$$r.{RAW_REF_FIELD}",
               "determination": f"$$r.{RAW_DETERMINATION_FIELD}",
               "findings_excerpt": {"$substrCP": [
                   {"$ifNull": [f"$$r.{RAW_FINDINGS_FIELD}", ""]}, 0, 240]}}}}

    pipeline = [
        {"$vectorSearch": {"index": VECTOR_INDEX, "path": "search_text",
                           "query": case["denial_text"][:4000],
                           "exact": True, "limit": 50}},
        {"$addFields": {"similarity": {"$meta": "vectorSearchScore"}}},
        {"$facet": {
            "strategies": [
                {"$unwind": "$strategy_ids"},
                {"$match": {"strategy_ids": {"$nin": failed}}},   # <-- the exclusion. THE product.
                {"$group": {"_id": "$strategy_ids",
                            "n": {"$sum": 1},
                            "overturns": {"$sum": {"$cond": [
                                {"$eq": ["$outcome", OUTCOME_OVERTURNED]}, 1, 0]}},
                            "similarity": {"$avg": "$similarity"},
                            "source_ids": {"$addToSet": "$source_id"}}},
                {"$match": {"n": {"$gte": MIN_SAMPLE}}},
                {"$addFields": {"overturn_rate": {"$divide": ["$overturns", "$n"]}}},
                {"$sort": {"overturn_rate": -1, "n": -1}},
                {"$limit": 5},
                {"$lookup": {"from": IMR_DECISIONS, "localField": "source_ids",
                             "foreignField": RAW_REF_FIELD, "as": "source_rows"}},
                {"$lookup": {"from": STRATEGIES, "localField": "_id",
                             "foreignField": "_id", "as": "info"}},
                {"$unwind": "$info"},
                {"$addFields": {"citations": citations_map}},
                {"$unset": ["source_rows", "source_ids"]},
            ],
            "evidence": [
                {"$match": {"outcome": OUTCOME_OVERTURNED}},
                {"$unwind": "$evidence_present"},
                {"$group": {"_id": "$evidence_present", "in_overturned": {"$sum": 1}}},
                {"$sort": {"in_overturned": -1}},
                {"$limit": 8},
                {"$lookup": {"from": EVIDENCE_TYPES, "localField": "_id",
                             "foreignField": "_id", "as": "info"}},
                {"$unwind": {"path": "$info", "preserveNullAndEmptyArrays": True}},
            ],
            "overall": [
                {"$group": {"_id": None, "n": {"$sum": 1},
                            "overturned": {"$sum": {"$cond": [
                                {"$eq": ["$outcome", OUTCOME_OVERTURNED]}, 1, 0]}}}},
            ],
        }},
    ]
    res = list(db[DENIAL_PROFILES].aggregate(pipeline))[0]

    overall = res["overall"][0] if res["overall"] else {"n": 0, "overturned": 0}
    have = set(case.get("evidence_have", []))
    missing = next(
        ({"evidence_id": e["_id"],
          "name": e.get("info", {}).get("name", e["_id"]),
          "description": e.get("info", {}).get("description", ""),
          "seen_in_overturned": e["in_overturned"],
          "overturned_total": overall["overturned"]}
         for e in res["evidence"] if e["_id"] not in have), None)

    strategies = [{"strategy_id": s["_id"], "name": s["info"]["name"],
                   "description": s["info"]["description"],
                   "example_phrasing": s["info"].get("example_phrasing", ""),
                   "n": s["n"], "overturns": s["overturns"],
                   "overturn_rate": round(s["overturn_rate"], 2),
                   "citations": s.get("citations", [])}
                  for s in res["strategies"]]

    return {"similar_cases": overall["n"],
            "overall_overturn_rate": (round(overall["overturned"] / overall["n"], 2)
                                      if overall["n"] else 0),
            "strategies": strategies,
            "missing_evidence": missing,
            "excluded_ids": failed}


def excluded_details(case_id: ObjectId) -> list:
    rows = list(db[ATTEMPTS].find({"case_id": case_id, "outcome": OUTCOME_UPHELD}))
    names = {s["_id"]: s["name"] for s in db[STRATEGIES].find(
        {"_id": {"$in": [r["strategy_id"] for r in rows]}})}
    return [{"strategy_id": r["strategy_id"],
             "name": names.get(r["strategy_id"], r["strategy_id"]),
             "recorded_at": r["recorded_at"].isoformat()} for r in rows]
```

- [ ] **Step 3: Write `main.py` — part 3: the Task-2 endpoints**

```python
@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/api/meta")
def meta():
    return {"evidence_types": list(db[EVIDENCE_TYPES].find()),
            "strategies": list(db[STRATEGIES].find())}


@app.post("/api/case")
def create_case(body: CaseIn):
    denial_date = (datetime.strptime(body.denial_date, "%Y-%m-%d")
                   if body.denial_date else utcnow())
    doc = {"created_at": utcnow(), "denial_text": body.denial_text,
           "denial_date": denial_date, "evidence_have": body.evidence_have,
           "stage": "intake", "deadlines": deadlines_for(denial_date)}
    cid = db[CASES].insert_one(doc).inserted_id
    return {"case_id": str(cid),
            "deadlines": {k: iso(v) for k, v in doc["deadlines"].items()}}


@app.post("/api/case/{cid}/analyze")
def analyze(cid: str):
    case = get_case(cid)
    result = rank_strategies(case)
    result["case_id"] = cid
    result["excluded"] = excluded_details(case["_id"])
    result["deadlines"] = {k: iso(v) for k, v in case["deadlines"].items()}
    result["stage"] = case["stage"]
    return result
```

- [ ] **Step 4: Acceptance — ranked output from fixtures**

```bash
uvicorn main:app --reload --port 8000 &
python - <<'EOF'
import requests
letter = open("demo/denial_letter.txt").read()
c = requests.post("http://localhost:8000/api/case", json={
    "denial_text": letter, "denial_date": "2026-07-20",
    "evidence_have": ["physician-letter"]}).json()
r = requests.post(f"http://localhost:8000/api/case/{c['case_id']}/analyze").json()
print("similar:", r["similar_cases"], "| overall:", r["overall_overturn_rate"])
for s in r["strategies"]:
    print(f'  {s["overturn_rate"]:.0%}  {s["name"]}  (won {s["overturns"]} of {s["n"]})')
print("missing:", r["missing_evidence"]["name"] if r["missing_evidence"] else None)
EOF
```

Expected: `similar: 20`, 3–5 ranked strategies with `cite-clinical-guideline`'s name near the top, each with a rate and sample size, and `missing: Named guideline excerpt`. If `$facet` after `$vectorSearch` errors on the sandbox version → Appendix B (two-aggregation split, 5 minutes).

- [ ] **Step 5: Commit**

```bash
git add main.py && git commit -m "feat: ranking aggregation — vectorSearch -> facet stats + provenance

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

**Event prompt (paste at 1:50):**

> Read `schema.py`. Build `main.py`: FastAPI app "Rebuttal", single file, matching the reference implementation in my plan (pasted below): module-level `MongoClient` from `MONGODB_URI`, LangSmith-wrapped Fireworks client with OpenRouter fallback in an `llm(messages)` helper (honor `STUB_LLM`), pydantic models `CaseIn`/`OutcomeIn`, helpers `get_case`/`deadlines_for` (180 days internal, +120 external), and the core `rank_strategies(case)` aggregation: `$vectorSearch` on `denial_profiles.search_text` (index `profiles_vector`, text `query`, `exact: True`, limit 50) → `$facet` with per-strategy `$unwind`/`$group` (n, overturns, overturn_rate, `$lookup` provenance from `imr_decisions` and names from `strategies`), evidence frequency among overturned, and overall stats — with a `$match` excluding any `strategy_ids` in this case's failed attempts (fetched via `distinct` first). Endpoints: `GET /` (serves static/index.html), `GET /api/meta`, `POST /api/case`, `POST /api/case/{cid}/analyze`. Then run the acceptance snippet from my plan and show me the ranked output.

---

### Task 3: Exclusion loop — draft records attempts, outcomes flip rankings (2:40–3:20)

**This is the project.** Same input, different output after a recorded loss — verified by script, not by assumption.

**Files:**
- Modify: `main.py` (append draft + outcome endpoints)
- Create: `test_exclusion.py`

**Interfaces:**
- Consumes: `rank_strategies`, `excluded_details`, `llm`, `get_case`, `OutcomeIn` (Task 2).
- Produces:
  - `do_draft(case: dict) -> {"strategy": <ranked strategy dict>, "letter": str}` — records a `pending` attempt (Task 6 reuses this).
  - `resolve_pending(case: dict, outcome: str) -> str` — resolves the latest pending attempt, `$inc`s strategy stats, updates stage, returns the strategy_id; raises 409 if no pending attempt (Task 6 reuses this — the lifecycle graph must record losses through the same code path, or exclusion won't fire on escalation).
  - HTTP: `POST /api/case/{cid}/draft` → `{"case_id", "strategy", "letter"}`; `POST /api/case/{cid}/outcome` body `{"outcome"}` → `{"case_id", "recorded", "strategy_id"}`.

- [ ] **Step 1: Append the drafting prompt + `do_draft` to `main.py`**

```python
DRAFT_SYSTEM = """You write internal-appeal letters for health-insurance claim denials on behalf of a patient.
Rules:
- Build the ENTIRE argument around the single strategy provided. Do not blend in other argument types.
- Never use any strategy listed under "DO NOT USE" — those already failed for this patient.
- Use only facts present in the denial letter and the evidence list. Invent nothing clinical; where a needed detail is unknown, write a [bracketed placeholder].
- Reference the appeal deadline. Request a written response with clinical rationale.
- Tone: firm, plain, professional. First person, patient's voice. Maximum one page.
Output only the letter text."""


def build_draft_prompt(case: dict, strategy: dict, missing, excluded: list) -> str:
    excluded_txt = "\n".join(f"- {e['name']}" for e in excluded) or "- (none)"
    missing_txt = (f"The patient does NOT yet have: {missing['name']}. "
                   f"Add one sentence noting it is being obtained."
                   if missing else "No missing evidence to mention.")
    return f"""DENIAL LETTER (verbatim from insurer):
---
{case['denial_text']}
---

STRATEGY TO USE (the only argument structure allowed):
{strategy['name']}: {strategy['description']}
Model phrasing: "{strategy['example_phrasing']}"
Track record: overturned {strategy['overturns']} of {strategy['n']} similar California IMR cases.

EVIDENCE THE PATIENT HAS: {', '.join(case.get('evidence_have', [])) or 'none listed'}
{missing_txt}

DO NOT USE (already tried by this patient and denied on appeal):
{excluded_txt}

APPEAL DEADLINE: {iso(case['deadlines']['internal_appeal_due'])}

Write the appeal letter."""


def do_draft(case: dict) -> dict:
    ranked = rank_strategies(case)
    if not ranked["strategies"]:
        raise HTTPException(409, "no strategies left — every known argument has been excluded")
    top = ranked["strategies"][0]
    excluded = excluded_details(case["_id"])
    letter = llm([{"role": "system", "content": DRAFT_SYSTEM},
                  {"role": "user", "content": build_draft_prompt(
                      case, top, ranked["missing_evidence"], excluded)}])
    db[ATTEMPTS].insert_one({"case_id": case["_id"], "strategy_id": top["strategy_id"],
                             "stage": case["stage"], "outcome": "pending",
                             "recorded_at": utcnow(), "letter": letter})
    db[CASES].update_one({"_id": case["_id"]}, {"$set": {"stage": "drafted"}})
    return {"strategy": top, "letter": letter}
```

- [ ] **Step 2: Append the draft + outcome endpoints to `main.py`**

```python
@app.post("/api/case/{cid}/draft")
def draft(cid: str):
    return {"case_id": cid, **do_draft(get_case(cid))}


def resolve_pending(case: dict, outcome: str) -> str:
    """Record how the latest filed appeal landed. Shared by the HTTP endpoint and
    the LangGraph lifecycle so exclusion fires identically on both paths."""
    attempt = db[ATTEMPTS].find_one({"case_id": case["_id"], "outcome": "pending"},
                                    sort=[("recorded_at", -1)])
    if not attempt:
        raise HTTPException(409, "no pending attempt to record an outcome for")
    db[ATTEMPTS].update_one({"_id": attempt["_id"]},
                            {"$set": {"outcome": outcome, "resolved_at": utcnow()}})
    # cross-user learning: this strategy's rolling stats move for EVERYONE
    db[STRATEGIES].update_one(
        {"_id": attempt["strategy_id"]},
        {"$inc": {"stats.attempts": 1,
                  "stats.overturns": 1 if outcome == OUTCOME_OVERTURNED else 0}})
    db[CASES].update_one(
        {"_id": case["_id"]},
        {"$set": {"stage": "won" if outcome == OUTCOME_OVERTURNED else "responded"}})
    return attempt["strategy_id"]


@app.post("/api/case/{cid}/outcome")
def record_outcome(cid: str, body: OutcomeIn):
    if body.outcome not in (OUTCOME_UPHELD, OUTCOME_OVERTURNED):
        raise HTTPException(422, "outcome must be 'upheld' or 'overturned'")
    strategy_id = resolve_pending(get_case(cid), body.outcome)
    return {"case_id": cid, "recorded": body.outcome, "strategy_id": strategy_id}
```

- [ ] **Step 3: Write `test_exclusion.py` — the spec's acceptance test, as a script**

```python
"""THE acceptance test: same denial letter, different ranking after a recorded loss.
Run with the server up:  STUB_LLM=1 uvicorn main:app --port 8000  (stub is fine here)."""
import requests

BASE = "http://localhost:8000"
LETTER = open("demo/denial_letter.txt").read()

case = requests.post(f"{BASE}/api/case", json={
    "denial_text": LETTER, "denial_date": "2026-07-20",
    "evidence_have": ["physician-letter"]}).json()
cid = case["case_id"]

r1 = requests.post(f"{BASE}/api/case/{cid}/analyze").json()
assert r1["strategies"], "no ranked strategies — is the vector index queryable?"
ids1 = [s["strategy_id"] for s in r1["strategies"]]
top1 = ids1[0]

d = requests.post(f"{BASE}/api/case/{cid}/draft").json()
assert d["strategy"]["strategy_id"] == top1

requests.post(f"{BASE}/api/case/{cid}/outcome", json={"outcome": "upheld"})

r2 = requests.post(f"{BASE}/api/case/{cid}/analyze").json()
ids2 = [s["strategy_id"] for s in r2["strategies"]]

assert top1 not in ids2, f"FAIL: excluded strategy {top1} still ranked"
assert ids1 != ids2, "FAIL: ranking unchanged after recorded loss"
assert top1 in [e["strategy_id"] for e in r2["excluded"]], "FAIL: loss not surfaced in excluded list"

d2 = requests.post(f"{BASE}/api/case/{cid}/draft").json()
assert d2["strategy"]["strategy_id"] != top1, "FAIL: redrafted with the failed strategy"

print(f"PASS: exclusion works — {top1} -> {ids2[0]}")
```

- [ ] **Step 4: Run it**

Run: `python test_exclusion.py`
Expected: `PASS: exclusion works — cite-clinical-guideline -> failed-alternatives` (exact slugs may vary with fixture stats; the assertion is what matters).

- [ ] **Step 5: Commit**

```bash
git add main.py test_exclusion.py && git commit -m "feat: exclusion loop — attempts memory changes rankings and drafts

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

**Event prompt (paste at 2:40):**

> Extend `main.py` per the reference in my plan (pasted below): add `DRAFT_SYSTEM` + `build_draft_prompt` + `do_draft(case)` (picks the top non-excluded strategy from `rank_strategies`, calls `llm`, inserts a `pending` attempt with the letter, sets stage "drafted"), plus `POST /api/case/{cid}/draft` and `POST /api/case/{cid}/outcome` (resolves the latest pending attempt, `$inc`s `strategies.stats`, updates stage). Then write `test_exclusion.py` exactly as in the plan and run it with `STUB_LLM=1`. Do not tell me it works — show me the PASS line. If it fails, debug until the same letter genuinely re-ranks after the recorded loss.

---

### Task 4: The 3:15 swap — fixtures out, real corpus in (3:15–3:30, joint)

A drives; B verifies. **Order matters: verify real data first, delete fixtures second.**

**Files:**
- Modify: `schema.py` (`MIN_SAMPLE` only — permitted tuning constant)

**Interfaces:**
- Consumes: A's real `denial_profiles` (~2,000, `is_fixture` absent), real `imr_decisions`, strategy stats.
- Produces: fixture-free corpus; `test_exclusion.py` green on real data.

- [ ] **Step 1: The 3:15 stand-up question:** is the exclusion logic working, yes or no? (You have the PASS line from Task 3 — show it.) If Task 3 is NOT green: A drops everything and pairs on it; skip Task 6 entirely.

- [ ] **Step 2: Verify real data alongside fixtures** — `python probe_search.py`: real profiles should now appear among hits. If A's new docs aren't matching, the index may still be embedding the new batch — wait for `create_index.py` polling to print READY again.

- [ ] **Step 3: Check A's strategy slugs.** `python -c "..."`:

```bash
python - <<'EOF'
import os
from dotenv import load_dotenv; load_dotenv()
from pymongo import MongoClient
from schema import DB_NAME, DENIAL_PROFILES, STRATEGIES
db = MongoClient(os.environ["MONGODB_URI"])[DB_NAME]
used = set(sid for p in db[DENIAL_PROFILES].find({}, {"strategy_ids": 1}) for sid in p.get("strategy_ids", []))
known = set(s["_id"] for s in db[STRATEGIES].find({}, {"_id": 1}))
print("slugs missing catalog entries:", used - known or "none")
EOF
```

Expected: `none` (A's extraction uses the closed vocabulary). Any stragglers: A adds catalog entries; do NOT rename slugs.

- [ ] **Step 4: Delete fixtures, retune, re-verify**

```bash
python - <<'EOF'
import os
from dotenv import load_dotenv; load_dotenv()
from pymongo import MongoClient
from schema import DB_NAME, DENIAL_PROFILES, IMR_DECISIONS
db = MongoClient(os.environ["MONGODB_URI"])[DB_NAME]
print("profiles removed:", db[DENIAL_PROFILES].delete_many({"is_fixture": True}).deleted_count)
print("raw removed:", db[IMR_DECISIONS].delete_many({"is_fixture": True}).deleted_count)
EOF
```

Edit `schema.py`: `MIN_SAMPLE = 3`. Then: `python test_exclusion.py` (fresh case → real rankings). Expected: PASS, with `similar: 50` and real sample sizes.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: real DMHC corpus behind rankings; fixtures removed

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: The UI + live drafting (3:20–3:50)

**Files:**
- Create: `static/index.html`
- Modify: `.env` (remove `STUB_LLM`, confirm `FIREWORKS_API_KEY`)

**Interfaces:**
- Consumes: `GET /api/meta`, `POST /api/case`, `/analyze`, `/draft`, `/outcome` (Tasks 2–3, exact response shapes above).
- Produces: the demo surface. One page, no charts, no dashboard. The visible thing is the intelligence: rates, sample sizes, the EXCLUDED card, the changed draft.

- [ ] **Step 1: Write `static/index.html` (complete file)**

```html
<!doctype html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rebuttal</title>
<style>
  :root{--bg:#0f1115;--card:#181b22;--ink:#e8eaf0;--dim:#8b93a7;--accent:#4f8cff;--win:#2ecc71;--lose:#e74c3c;--warn:#f5a623}
  *{box-sizing:border-box;margin:0}
  body{background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,system-ui,sans-serif;max-width:880px;margin:0 auto;padding:24px}
  h1{font-size:22px} h3{font-size:15px}
  .sub{color:var(--dim);font-size:13px;margin:4px 0 20px}
  textarea{width:100%;height:150px;background:var(--card);color:var(--ink);border:1px solid #2a2f3a;border-radius:8px;padding:12px;font:13px/1.4 ui-monospace,monospace}
  .row{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:10px 0}
  input[type=date]{background:var(--card);color:var(--ink);border:1px solid #2a2f3a;border-radius:6px;padding:6px}
  label.ev{font-size:13px;color:var(--dim);display:inline-flex;gap:4px;align-items:center}
  button{background:var(--accent);border:0;color:#fff;padding:10px 18px;border-radius:8px;font-size:14px;cursor:pointer}
  button.ghost{background:#2a2f3a} button:disabled{opacity:.5}
  .card{background:var(--card);border:1px solid #2a2f3a;border-radius:10px;padding:14px;margin:10px 0}
  .card.excluded{opacity:.55;border-color:var(--lose)} .card.excluded h3{text-decoration:line-through}
  .rate{float:right;font-weight:700} .win{color:var(--win)} .dim{color:var(--dim);font-size:13px}
  .callout{border-left:4px solid var(--warn)}
  .tag{font-size:11px;background:#2a2f3a;border-radius:4px;padding:2px 6px;color:var(--dim)}
  pre{white-space:pre-wrap;font:13px/1.5 ui-monospace,monospace;background:#0b0d11;padding:14px;border-radius:8px}
  .stat{font-size:17px;margin:14px 0 6px}
  #results,#draftbox{display:none}
</style></head>
<body>
<h1>Rebuttal</h1>
<div class="sub">Appeals that remember. Outcome data: California DMHC Independent Medical Review
records via the CHHS Open Data Portal (DMHC / Office of the Patient Advocate). Noncommercial
demo built at the MongoDB Persistent Context Sprint. Not legal or medical advice.</div>

<textarea id="letter" placeholder="Paste the denial letter here…"></textarea>
<div class="row">
  <span class="dim">Denial date:</span><input type="date" id="ddate">
  <span id="evlist"></span>
</div>
<button id="go" onclick="analyze()">Analyze this denial</button>

<div id="results">
  <div class="stat" id="headline"></div>
  <div class="dim" id="deadline"></div>
  <div class="card callout" id="missing"></div>
  <div id="strategies"></div>
  <div id="excluded"></div>
  <button id="draftbtn" onclick="draft()">Draft the appeal</button>
</div>

<div id="draftbox">
  <h1 style="font-size:17px;margin-top:20px">Appeal draft <span class="tag" id="usedstrat"></span></h1>
  <pre id="draft"></pre>
  <div class="row">
    <span class="dim">When the insurer responds:</span>
    <button class="ghost" onclick="outcome('upheld')">Denial upheld</button>
    <button onclick="outcome('overturned')">Overturned 🎉</button>
  </div>
</div>

<script>
let caseId = null;
const $ = id => document.getElementById(id);

async function api(path, body){
  const r = await fetch(path, {method:'POST', headers:{'content-type':'application/json'},
                               body: body ? JSON.stringify(body) : null});
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}

(async () => {   // evidence checkboxes from the catalog
  const meta = await (await fetch('/api/meta')).json();
  $('evlist').innerHTML = meta.evidence_types.map(e =>
    `<label class="ev"><input type="checkbox" value="${e._id}">${e.name}</label>`).join(' ');
})();

async function analyze(){
  if(!caseId){
    const have = [...document.querySelectorAll('#evlist input:checked')].map(c => c.value);
    const c = await api('/api/case', {denial_text: $('letter').value,
                                      denial_date: $('ddate').value || null,
                                      evidence_have: have});
    caseId = c.case_id;
  }
  const r = await api(`/api/case/${caseId}/analyze`);
  $('results').style.display = 'block';
  $('headline').innerHTML = `Based on <b>${r.similar_cases}</b> similar California IMR cases —
    <b class="win">${Math.round(r.overall_overturn_rate*100)}%</b> were overturned.`;
  $('deadline').textContent = `Internal appeal deadline: ${r.deadlines.internal_appeal_due}
    · External review window after that: ${r.deadlines.external_review_due}`;
  $('missing').style.display = r.missing_evidence ? 'block' : 'none';
  if(r.missing_evidence) $('missing').innerHTML =
    `<b>The document you're missing:</b> ${r.missing_evidence.name} —
     present in ${r.missing_evidence.seen_in_overturned} of the
     ${r.missing_evidence.overturned_total} overturned similar cases.`;
  $('strategies').innerHTML = r.strategies.map((s,i) => `
    <div class="card"><span class="rate win">${Math.round(s.overturn_rate*100)}%</span>
      <h3>${i+1}. ${s.name}</h3>
      <div class="dim">${s.description}</div>
      <div class="dim">Won ${s.overturns} of ${s.n} similar cases
        ${s.citations[0] ? '· e.g. IMR case ' + s.citations[0].ref : ''}</div>
    </div>`).join('');
  $('excluded').innerHTML = r.excluded.map(e => `
    <div class="card excluded"><span class="rate">EXCLUDED</span>
      <h3>${e.name}</h3>
      <div class="dim">You already appealed with this and the denial was upheld.
        It will not be suggested to you again.</div>
    </div>`).join('');
}

async function draft(){
  $('draftbtn').disabled = true;
  try{
    const d = await api(`/api/case/${caseId}/draft`);
    $('draftbox').style.display = 'block';
    $('usedstrat').textContent = d.strategy.name;
    $('draft').textContent = d.letter;
  } finally { $('draftbtn').disabled = false; }
}

async function outcome(o){
  await api(`/api/case/${caseId}/outcome`, {outcome: o});
  if(o === 'upheld'){ await analyze(); await draft(); }  // beat two, live: re-rank + new argument
  else { $('headline').innerHTML =
    '🎉 Denial overturned. Recorded — the next patient\'s ranking just got smarter.'; }
}
</script>
</body></html>
```

- [ ] **Step 2: Go live on LLM drafting.** Remove `STUB_LLM` from `.env`; confirm `FIREWORKS_API_KEY` (redeemed `MONGODB813`). Verify the Fireworks model id in their model library and update `FW_MODEL` if needed. Restart uvicorn.

- [ ] **Step 3: Acceptance — the full demo loop in a browser.** Open `http://localhost:8000`: paste `demo/denial_letter.txt`, set date 2026-07-20, check only "Letter of medical necessity" → Analyze → ranked cards + missing-evidence callout → Draft (a real letter, built on the #1 strategy) → "Denial upheld" → watch: EXCLUDED card appears struck through, ranking re-orders, a NEW draft on a different argument renders without you touching anything. That auto-refresh IS beat two.

- [ ] **Step 4: Check the LangSmith project `rebuttal`** — draft calls should be appearing as traces (your 3:15-debugging parachute, and partner-tool evidence for judges).

- [ ] **Step 5: Commit**

```bash
git add static/index.html && git commit -m "feat: demo UI — ranked strategies, exclusion cards, live redraft

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

**Event prompt (paste at 3:20):**

> Create `static/index.html` matching the reference in my plan (pasted below): dark single page, no charts — paste box, denial-date input, evidence checkboxes populated from `GET /api/meta`, Analyze button → headline stat + deadline line + missing-evidence callout + ranked strategy cards (rate, name, description, "Won X of N similar cases", first citation ref) + EXCLUDED cards (struck-through, red border) → Draft button → letter + two outcome buttons. On "Denial upheld" it must automatically re-analyze AND re-draft so the re-ranking and the new argument happen on screen in one motion. Keep it under ~200 lines. Then walk me through the full loop against the running server.

---

### Task 6: LangGraph lifecycle with Atlas checkpoints (3:50–4:15) — FIRST CUT if slipping

Skip without guilt if Tasks 1–5 aren't all green. The demo does not depend on this; it's depth on the MongoDB + LangChain judging criteria.

**Files:**
- Create: `lifecycle.py`
- Modify: `main.py` (3-line guarded include at the very bottom)

**Interfaces:**
- Consumes: `client`, `get_case`, `rank_strategies`, `do_draft`, `resolve_pending`, `OutcomeIn` from `main`; `DB_NAME`, `OUTCOME_UPHELD` from `schema`.
- Produces: `POST /api/case/{cid}/lifecycle/start`, `POST /api/case/{cid}/lifecycle/resume`; checkpoints visible in Atlas (`checkpoints*` collections) — thread_id == case_id.

- [ ] **Step 1: Write `lifecycle.py`**

```python
"""Appeal lifecycle as a long-running state machine: draft -> file -> suspend
(weeks pass) -> resume on insurer response -> escalate with a new argument.
Checkpoints persist to Atlas via langgraph-checkpoint-mongodb, so the graph
resumes months later exactly where it left off. Thread id == case id."""
from typing import TypedDict

from fastapi import APIRouter
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from main import OutcomeIn, client, do_draft, get_case, rank_strategies, resolve_pending
from schema import DB_NAME, OUTCOME_UPHELD


class AppealState(TypedDict, total=False):
    case_id: str
    top_strategy: str
    n_ranked: int
    letter: str
    outcome: str


def analyze_node(state: AppealState):
    ranked = rank_strategies(get_case(state["case_id"]))
    return {"n_ranked": len(ranked["strategies"])}


def draft_node(state: AppealState):
    d = do_draft(get_case(state["case_id"]))
    return {"letter": d["letter"], "top_strategy": d["strategy"]["strategy_id"]}


def await_insurer(state: AppealState):
    # Suspends the graph — checkpoint sits in Atlas until the response arrives.
    return {"outcome": interrupt("filed — waiting on insurer response")}


def record_node(state: AppealState):
    # Same code path as POST /outcome — without this write, the loss never
    # lands in `attempts` and the escalation would reuse the failed strategy.
    resolve_pending(get_case(state["case_id"]), state["outcome"])
    return {}


def route(state: AppealState):
    return "analyze" if state["outcome"] == OUTCOME_UPHELD else END


g = StateGraph(AppealState)
g.add_node("analyze", analyze_node)
g.add_node("draft", draft_node)
g.add_node("await_insurer", await_insurer)
g.add_node("record", record_node)
g.add_edge(START, "analyze")
g.add_edge("analyze", "draft")
g.add_edge("draft", "await_insurer")
g.add_edge("await_insurer", "record")
g.add_conditional_edges("record", route, {"analyze": "analyze", END: END})

appeal_graph = g.compile(checkpointer=MongoDBSaver(client, db_name=DB_NAME))

router = APIRouter()


def _clean(state: dict) -> dict:
    return {k: v for k, v in state.items() if not k.startswith("__")}


@router.post("/api/case/{cid}/lifecycle/start")
def lifecycle_start(cid: str):
    out = appeal_graph.invoke({"case_id": cid},
                              {"configurable": {"thread_id": cid}})
    return _clean(out)


@router.post("/api/case/{cid}/lifecycle/resume")
def lifecycle_resume(cid: str, body: OutcomeIn):
    out = appeal_graph.invoke(Command(resume=body.outcome),
                              {"configurable": {"thread_id": cid}})
    return _clean(out)
```

- [ ] **Step 2: Wire into `main.py` — MUST stay at the very bottom of the file (bottom import breaks the circular-import knot)**

```python
try:
    from lifecycle import router as lifecycle_router
    app.include_router(lifecycle_router)
except Exception as e:   # lifecycle is optional; never let it take down the demo
    print(f"lifecycle disabled: {e}")
```

- [ ] **Step 3: Acceptance**

```bash
python - <<'EOF'
import requests
BASE = "http://localhost:8000"
c = requests.post(f"{BASE}/api/case", json={
    "denial_text": open("demo/denial_letter.txt").read(),
    "denial_date": "2026-07-20", "evidence_have": ["physician-letter"]}).json()
cid = c["case_id"]
s1 = requests.post(f"{BASE}/api/case/{cid}/lifecycle/start").json()
print("suspended after drafting with:", s1.get("top_strategy"))
s2 = requests.post(f"{BASE}/api/case/{cid}/lifecycle/resume", json={"outcome": "upheld"}).json()
print("resumed + escalated with:", s2.get("top_strategy"))
assert s1.get("top_strategy") != s2.get("top_strategy"), "escalation reused the failed strategy"
print("PASS: lifecycle suspends, resumes, and escalates with a different argument")
EOF
```

Expected: two different strategy slugs and the PASS line. Then check Atlas: `checkpoints`/`checkpoint_writes` collections exist with your case_id as thread_id — screenshot-worthy for beat three. (If the `MongoDBSaver(client, db_name=...)` signature errors, check the installed package's README — `MongoDBSaver.from_conn_string(os.environ["MONGODB_URI"])` is the alternate constructor.)

- [ ] **Step 4: Commit**

```bash
git add lifecycle.py main.py && git commit -m "feat: LangGraph appeal lifecycle checkpointed to Atlas

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

**Event prompt (paste at 3:50, only if Tasks 1–5 are green):**

> Create `lifecycle.py` per the reference in my plan (pasted below): a LangGraph `StateGraph` (analyze → draft → await_insurer with `interrupt()` → record via `resolve_pending`, conditional edge back to analyze on "upheld") compiled with `MongoDBSaver` against our Atlas client, plus an `APIRouter` with `/lifecycle/start` and `/lifecycle/resume` endpoints using thread_id == case_id, included from the bottom of `main.py` inside a try/except. The record node is load-bearing: without it the loss never reaches `attempts` and escalation reuses the failed strategy. Run the plan's acceptance snippet and show me both strategy slugs and the Atlas checkpoint collections.

---

### Task 7: Ship it — video, README, public repo, submission (4:15–5:00)

**Files:**
- Modify: `README.md`
- Produce: the one-minute video, the submission.

**Interfaces:**
- Consumes: the working demo loop (Task 5), reseeded to a clean state.
- Produces: round-one submission. **A working project nobody recorded scores zero.**

- [ ] **Step 1 (4:15): Reset demo state** — fresh case history so the video shows first-contact behavior:

```bash
python - <<'EOF'
import os
from dotenv import load_dotenv; load_dotenv()
from pymongo import MongoClient
from schema import DB_NAME, CASES, ATTEMPTS
db = MongoClient(os.environ["MONGODB_URI"])[DB_NAME]
db[CASES].delete_many({}); db[ATTEMPTS].delete_many({})
print("demo state reset")
EOF
```

Have open before recording: the app at `localhost:8000`, and Atlas UI on the `attempts` + `denial_profiles` collections tab.

- [ ] **Step 2 (4:15–4:35): Record the 60-second video.** One person drives, one watches. Script (timings tight — rehearse once):

  - **0:00–0:08 — hook.** App visible, letter already pasted. Say: *"Insurers remember every appeal ever filed. Patients start from zero. Rebuttal fixes the asymmetry — appeal tools that generate a letter and forget you exist; ours remembers what's been tried, by you and by everyone before you."*
  - **0:08–0:25 — beat one.** Click Analyze. Point at the numbers: *"Real California IMR records: N similar denials, X% overturned. These are the argument structures that actually won — with sample sizes — and this is the document I'm missing that appears in most of the overturned cases."* Click Draft.
  - **0:25–0:48 — beat two (the whole demo).** Click "Denial upheld". As the screen re-ranks and redrafts on its own: *"The insurer said no. Watch — the losing argument is now EXCLUDED for me, the ranking re-orders, and the next draft is already built on a different argument. Every other tool in this space would hand you the same letter again."*
  - **0:48–1:00 — beat three + close.** Flash the Atlas `attempts` doc + a `denial_profiles` doc: *"It's all state in Atlas — provenance, sample sizes, the exclusion. Fewer than one percent of denials get appealed; up to two-thirds of appeals win. Most people would win a fight they never enter."*

- [ ] **Step 3 (4:35–4:50): README + public repo.** Replace `README.md` with:

```markdown
# Rebuttal

Insurance denial appeals that remember — every appeal filed makes the next one
smarter, for you and for everyone else. Built in 3.5 hours at the MongoDB
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
`$vectorSearch` (Atlas automated embeddings, voyage-3-large, text query) →
`$match` excluding this user's failed strategies → `$facet` into per-strategy
overturn rates with `$lookup` provenance from raw `imr_decisions`, evidence
frequency among overturned neighbors, and overall stats. FastAPI + vanilla JS
on top; Fireworks drafts the letter (OpenRouter fallback); optional LangGraph
lifecycle checkpoints the months-long appeal process to Atlas via
langgraph-checkpoint-mongodb; LangSmith tracing on.

Run: `pip install -r requirements.txt`, fill `.env` (see `.env.example`),
`python fixtures.py && python create_index.py`, `uvicorn main:app`.

## What was built during the event vs. what is public data

- **Built today (all code in this repo):** `schema.py`, `main.py`, `ingest.py`,
  `fixtures.py`, `create_index.py`, `probe_search.py`, `test_exclusion.py`,
  `lifecycle.py`, `static/index.html` — see commit timestamps.
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
```

```bash
git add -A && git commit -m "docs: README with DMHC attribution and event provenance

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
gh repo create rebuttal --public --source=. --push
```

- [ ] **Step 4 (4:50–5:00): Submit.** Video + repo URL + both names on the submission page. Confirm the confirmation screen. **Not at 4:58.**

---

## Appendix A — Fallback: manual embeddings (~20 min, only if auto-embedding is unavailable)

1. Add to `main.py` (and import in `fixtures.py` / hand to A for `ingest.py`):

```python
EMBED_MODEL = "nomic-ai/nomic-embed-text-v1.5"   # verify exact id in Fireworks model library

def embed(text: str) -> list:
    return fireworks.embeddings.create(model=EMBED_MODEL,
                                       input=text[:8000]).data[0].embedding
```

2. On every `denial_profiles` insert, set `"embedding": embed(doc["search_text"])`.
3. Replace the index definition in `create_index.py`:

```python
definition={"fields": [{"type": "vector", "path": "embedding",
                        "numDimensions": 768, "similarity": "cosine"}]}
```

4. In `rank_strategies`, replace the `$vectorSearch` stage's `"query": ...` with
   `"queryVector": embed(case["denial_text"][:4000])` and change `"path"` to `"embedding"`.
5. Re-run `python fixtures.py && python create_index.py && python probe_search.py`
   (update the probe the same way).

## Appendix B — Fallback: if `$facet` after `$vectorSearch` errors

Split into three aggregations sharing the same head (costs two extra vector
searches on ≤2,000 docs — negligible):

```python
head = [
    {"$vectorSearch": {"index": VECTOR_INDEX, "path": "search_text",
                       "query": case["denial_text"][:4000], "exact": True, "limit": 50}},
    {"$addFields": {"similarity": {"$meta": "vectorSearchScore"}}},
]
res = {
    "strategies": list(db[DENIAL_PROFILES].aggregate(head + strategies_stages)),
    "evidence":   list(db[DENIAL_PROFILES].aggregate(head + evidence_stages)),
    "overall":    list(db[DENIAL_PROFILES].aggregate(head + overall_stages)),
}
```

where `strategies_stages` / `evidence_stages` / `overall_stages` are exactly the
three `$facet` arm lists from Task 2, lifted into named variables. The rest of
`rank_strategies` is unchanged.

## Appendix C — Hand to Person A at 1:45: the extraction prompt (closed vocabulary)

> You label California IMR case records. Given ONE case's findings text and its
> metadata, return ONLY this JSON:
> `{"strategy_ids": [...], "evidence_present": [...], "search_text": "..."}`
>
> **strategy_ids** — which of these argument archetypes the reviewer's reasoning
> actually relied on (0–3; use [] if none clearly apply; NEVER invent new ids):
> `cite-clinical-guideline` (named guideline establishes standard of care) ·
> `failed-alternatives` (plan-preferred alternative tried and failed/contraindicated) ·
> `peer-reviewed-evidence` (specific published studies) ·
> `treating-physician-rationale` (treating specialist's patient-specific necessity rationale) ·
> `plan-criteria-met` (insurer's own criteria satisfied/misapplied) ·
> `fda-approved-indication` (FDA approval / compendia listing for this use) ·
> `continuity-of-care` (interrupting effective treatment causes harm) ·
> `urgent-risk` (delay poses imminent/irreversible harm)
>
> **evidence_present** — documentation the findings credit:
> `physician-letter` · `clinical-guideline-citation` · `peer-reviewed-studies` ·
> `prior-treatment-records` · `imaging-test-results` · `specialist-second-opinion` ·
> `plan-policy-excerpt` · `fda-compendia-support`
>
> **search_text** — 40–90 words summarizing the DENIAL SITUATION (what was
> denied, the insurer's stated reason, patient context), written like a neutral
> case summary. **Do NOT mention or imply the outcome** — it would bias retrieval.
>
> (`outcome` is NOT extracted by the model — A derives it in `ingest.py` from the raw
> `Determination` column: startswith "Overturned" → "overturned", else "upheld".)

## Appendix D — Risk register

| Risk | Detect | Fallback | Cost |
|---|---|---|---|
| Auto-embedding not on sandbox tier | `probe_search.py` fails at ~1:48 | Appendix A | ~20 min |
| `$facet` rejected after `$vectorSearch` | Task 2 acceptance errors | Appendix B | ~5 min |
| Fireworks key/redeem delayed | draft 500s | `STUB_LLM=1` to keep building; OpenRouter fallback already wired | 0 |
| A's extraction is mush | 3:15 check-in | Closed vocabulary prevents it structurally; else A hand-curates 8 strategies (spec fallback) | A's lane |
| Real-data swap thins strategy samples | `test_exclusion.py` after swap | Keep `MIN_SAMPLE=2`; demo letter targets the densest category | ~2 min |
| Index still embedding A's 2k rows at 3:20 | probe returns only stale hits | Demo on fixtures until READY; delete fixtures ONLY after real-data probe passes | 0 |
| Exclusion not green at 3:15 | the stand-up question | A pairs on it; Task 6 skipped entirely | — |
| Beat two looks random | fixture stat targets in Task 1 | #1 and #2 strategies engineered to be distinct and specific | 0 |
