"""Rebuttal - insurance denial appeals that remember. Person B's service.

Outcome data: California DMHC Independent Medical Review records (CHHS Open
Data Portal). Noncommercial use. Not legal or medical advice.
"""
import os
import re
from datetime import datetime, timedelta
from typing import Optional

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pymongo import MongoClient

from schema import (COLL_ATTEMPTS, COLL_CASES, COLL_DECISIONS, COLL_EVIDENCE,
                    COLL_PROFILES, COLL_STRATEGIES, DETERMINATION_OVERTURNED,
                    DETERMINATION_UPHELD, EMBED_SOURCE, LEXICAL_INDEX, MIN_SAMPLE,
                    SRC_DETERMINATION, SRC_FINDINGS, SRC_REF, VECTOR_INDEX)

load_dotenv()
client = MongoClient(os.environ["MONGODB_URI"])
db = client[os.environ.get("MONGODB_DB", "rebuttal")]

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
_or_key = os.environ.get("OPENROUTER_API_KEY", "")
openrouter = (OpenAI(base_url="https://openrouter.ai/api/v1", api_key=_or_key)
              if (OpenAI and _or_key) else None)

app = FastAPI(title="Rebuttal")
app.mount("/static", StaticFiles(directory="static"), name="static")


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
    case = db[COLL_CASES].find_one({"_id": ObjectId(cid)})
    if not case:
        raise HTTPException(404, "case not found")
    return case


def deadlines_for(denial_date: datetime) -> dict:
    internal = denial_date + timedelta(days=180)          # internal appeal window
    return {"internal_appeal_due": internal,
            "external_review_due": internal + timedelta(days=120)}  # then external review


def _search_head(query_text: str) -> list:
    """First stages of the pipeline: vector search (auto-embedded text query) by
    default; SEARCH_MODE=lexical swaps in an Atlas Search text stage if the
    sandbox tier lacks automated embeddings."""
    if os.environ.get("SEARCH_MODE", "vector") == "lexical":
        return [
            {"$search": {"index": LEXICAL_INDEX,
                         "text": {"query": query_text, "path": EMBED_SOURCE}}},
            {"$limit": 50},
            {"$addFields": {"similarity": {"$meta": "searchScore"}}},
        ]
    return [
        {"$vectorSearch": {"index": VECTOR_INDEX, "path": EMBED_SOURCE,
                           "query": query_text, "exact": True, "limit": 50}},
        {"$addFields": {"similarity": {"$meta": "vectorSearchScore"}}},
    ]


# ---------------------------------------------------------------- the product
def rank_strategies(case: dict) -> dict:
    """search -> exclusion $match -> per-strategy stats + evidence + provenance.

    The $match on failed strategy keys is what makes this memory, not search:
    the same denial letter ranks differently after a recorded loss.
    """
    failed = db[COLL_ATTEMPTS].distinct(
        "strategy_id", {"case_id": case["_id"], "outcome": DETERMINATION_UPHELD})

    citations_map = {"$map": {
        "input": {"$slice": ["$source_rows", 3]}, "as": "r",
        "in": {"ref": f"$$r.{SRC_REF}",
               "determination": f"$$r.{SRC_DETERMINATION}",
               "findings_excerpt": {"$substrCP": [
                   {"$ifNull": [f"$$r.{SRC_FINDINGS}", ""]}, 0, 240]}}}}

    pipeline = _search_head(case["denial_text"][:4000]) + [
        {"$facet": {
            "strategies": [
                {"$unwind": "$strategy_keys"},
                {"$match": {"strategy_keys": {"$nin": failed}}},   # <-- the exclusion
                {"$group": {"_id": "$strategy_keys",
                            "n": {"$sum": 1},
                            "overturns": {"$sum": {"$cond": [
                                {"$eq": ["$determination", DETERMINATION_OVERTURNED]}, 1, 0]}},
                            "similarity": {"$avg": "$similarity"},
                            "source_ids": {"$addToSet": "$source_ref"}}},
                {"$match": {"n": {"$gte": MIN_SAMPLE}}},
                {"$addFields": {"overturn_rate": {"$divide": ["$overturns", "$n"]}}},
                {"$sort": {"overturn_rate": -1, "n": -1}},
                {"$limit": 5},
                {"$lookup": {"from": COLL_DECISIONS, "localField": "source_ids",
                             "foreignField": SRC_REF, "as": "source_rows"}},
                {"$lookup": {"from": COLL_STRATEGIES, "localField": "_id",
                             "foreignField": "_id", "as": "info"}},
                {"$unwind": {"path": "$info", "preserveNullAndEmptyArrays": True}},
                {"$addFields": {"citations": citations_map}},
                {"$unset": ["source_rows", "source_ids"]},
            ],
            "evidence": [
                {"$match": {"determination": DETERMINATION_OVERTURNED}},
                {"$unwind": "$evidence_keys"},
                {"$group": {"_id": "$evidence_keys", "in_overturned": {"$sum": 1}}},
                {"$sort": {"in_overturned": -1}},
                {"$limit": 8},
                {"$lookup": {"from": COLL_EVIDENCE, "localField": "_id",
                             "foreignField": "_id", "as": "info"}},
                {"$unwind": {"path": "$info", "preserveNullAndEmptyArrays": True}},
            ],
            "overall": [
                {"$group": {"_id": None, "n": {"$sum": 1},
                            "overturned": {"$sum": {"$cond": [
                                {"$eq": ["$determination", DETERMINATION_OVERTURNED]}, 1, 0]}}}},
            ],
        }},
    ]
    res = list(db[COLL_PROFILES].aggregate(pipeline))[0]

    overall = res["overall"][0] if res["overall"] else {"n": 0, "overturned": 0}
    have = set(case.get("evidence_have", []))

    def _ev(e):
        info = e.get("info") or {}
        return {"evidence_id": e["_id"],
                "name": info.get("name", e["_id"].replace("_", " ")),
                "description": info.get("description", ""),
                "seen_in_overturned": e["in_overturned"],
                "overturned_total": overall["overturned"]}

    missing = next((_ev(e) for e in res["evidence"] if e["_id"] not in have), None)

    strategies = []
    for s in res["strategies"]:
        info = s.get("info") or {}
        strategies.append(
            {"strategy_id": s["_id"],
             "name": info.get("name", s["_id"].replace("_", " ")),
             "description": info.get("description", ""),
             "example_phrasing": info.get("example_phrasing", ""),
             "n": s["n"], "overturns": s["overturns"],
             "overturn_rate": round(s["overturn_rate"], 2),
             "citations": s.get("citations", [])})

    return {"similar_cases": overall["n"],
            "overall_overturn_rate": (round(overall["overturned"] / overall["n"], 2)
                                      if overall["n"] else 0),
            "strategies": strategies,
            "missing_evidence": missing,
            "excluded_ids": failed}


def excluded_details(case_id: ObjectId) -> list:
    rows = list(db[COLL_ATTEMPTS].find({"case_id": case_id,
                                        "outcome": DETERMINATION_UPHELD}))
    names = {s["_id"]: s.get("name", s["_id"]) for s in db[COLL_STRATEGIES].find(
        {"_id": {"$in": [r["strategy_id"] for r in rows]}})}
    return [{"strategy_id": r["strategy_id"],
             "name": names.get(r["strategy_id"], r["strategy_id"].replace("_", " ")),
             "recorded_at": r["recorded_at"].isoformat()} for r in rows]


# ------------------------------------------------------------------ drafting
def compose_letter(case: dict, strategy: dict, missing) -> str:
    """Deterministic letter composer - every sentence is driven by stored state:
    the top non-excluded strategy, its live track record, the user's evidence
    list, and the computed deadline."""
    evidence_names = {e["_id"]: e.get("name", e["_id"]) for e in db[COLL_EVIDENCE].find()}
    have = [evidence_names.get(k, k.replace("_", " ")) for k in case.get("evidence_have", [])]
    basis = (strategy.get("example_phrasing") or strategy.get("description")
             or strategy["name"])
    lines = [
        f"Date: {utcnow().strftime('%B %d, %Y')}",
        "",
        "RE: Formal internal appeal of claim denial",
        f"Denial letter dated: {iso(case['denial_date'])}",
        "",
        "To the Appeals Department:",
        "",
        ("I am writing to formally appeal your denial of the requested service. "
         f"This appeal is filed within my appeal window, which runs through "
         f"{iso(case['deadlines']['internal_appeal_due'])}."),
        "",
        f"The central basis of this appeal: {basis} "
        "The clinical record accompanying this appeal supports this argument in my case.",
        (f"In {strategy['n']} comparable cases reviewed under California's Independent "
         f"Medical Review program, this argument prevailed in {strategy['overturns']} - "
         f"a {round(100 * strategy['overturn_rate'])}% overturn rate in independent review."),
        "",
    ]
    if have:
        lines.append("Enclosed with this appeal: " + "; ".join(have) + ".")
    if missing:
        lines.append("I am also obtaining the following documentation and will forward "
                     f"it upon receipt: {missing['name']}.")
    lines += [
        "",
        ("Please provide a written response including the clinical rationale for your "
         "determination and the specific plan criteria applied. If this denial is "
         "upheld, I will pursue Independent Medical Review through the California "
         "Department of Managed Health Care."),
        "",
        "Sincerely,",
        "[Member name]",
    ]
    return "\n".join(lines)


DRAFT_SYSTEM = """You write internal-appeal letters for health-insurance claim denials on behalf of a patient.
Rules:
- Build the ENTIRE argument around the single strategy provided. Do not blend in other argument types.
- Never use any strategy listed under "DO NOT USE" - those already failed for this patient.
- Use only facts present in the denial letter and the evidence list. Invent nothing clinical; where a needed detail is unknown, write a [bracketed placeholder].
- Reference the appeal deadline. Request a written response with clinical rationale.
- Tone: firm, plain, professional. First person, patient's voice. Maximum one page.
Output only the letter text."""


def build_draft_prompt(case: dict, strategy: dict, missing, excluded: list) -> str:
    excluded_txt = "\n".join(f"- {e['name']}" for e in excluded) or "- (none)"
    missing_txt = (f"The patient does NOT yet have: {missing['name']}. "
                   f"Add one sentence noting it is being obtained."
                   if missing else "No missing evidence to mention.")
    basis = (strategy.get("example_phrasing") or strategy.get("description")
             or strategy["name"])
    return f"""DENIAL LETTER (verbatim from insurer):
---
{case['denial_text']}
---

STRATEGY TO USE (the only argument structure allowed):
{strategy['name']}: {strategy.get('description', '')}
Model phrasing: "{basis}"
Track record: overturned {strategy['overturns']} of {strategy['n']} similar California IMR cases.

EVIDENCE THE PATIENT HAS: {', '.join(case.get('evidence_have', [])) or 'none listed'}
{missing_txt}

DO NOT USE (already tried by this patient and denied on appeal):
{excluded_txt}

APPEAL DEADLINE: {iso(case['deadlines']['internal_appeal_due'])}

Write the appeal letter."""


def llm_letter(case: dict, strategy: dict, missing, excluded: list):
    """OpenRouter draft; returns None on any failure so the deterministic
    composer takes over - a provider hiccup must never kill the demo."""
    if not openrouter:
        return None
    try:
        r = openrouter.chat.completions.create(
            model=OPENROUTER_MODEL, temperature=0.4, max_tokens=1100, timeout=25,
            messages=[{"role": "system", "content": DRAFT_SYSTEM},
                      {"role": "user", "content": build_draft_prompt(
                          case, strategy, missing, excluded)}])
        text = (r.choices[0].message.content or "").strip()
        text = re.sub("\\s*\u2014\\s*", " - ", text)  # no em dashes in output
        return text or None
    except Exception as e:
        print(f"openrouter draft failed ({e}); using deterministic composer")
        return None


def do_draft(case: dict) -> dict:
    ranked = rank_strategies(case)
    if not ranked["strategies"]:
        raise HTTPException(409, "no strategies left - every known argument has been excluded")
    top = ranked["strategies"][0]
    excluded = excluded_details(case["_id"])
    letter = (llm_letter(case, top, ranked["missing_evidence"], excluded)
              or compose_letter(case, top, ranked["missing_evidence"]))
    db[COLL_ATTEMPTS].insert_one({"case_id": case["_id"], "strategy_id": top["strategy_id"],
                                  "stage": case["stage"], "outcome": "pending",
                                  "recorded_at": utcnow(), "letter": letter})
    db[COLL_CASES].update_one({"_id": case["_id"]}, {"$set": {"stage": "drafted"}})
    return {"strategy": top, "letter": letter}


def resolve_pending(case: dict, outcome: str) -> str:
    """Record how the latest filed appeal landed. The write that makes memory."""
    attempt = db[COLL_ATTEMPTS].find_one({"case_id": case["_id"], "outcome": "pending"},
                                         sort=[("recorded_at", -1)])
    if not attempt:
        raise HTTPException(409, "no pending attempt to record an outcome for")
    db[COLL_ATTEMPTS].update_one({"_id": attempt["_id"]},
                                 {"$set": {"outcome": outcome, "resolved_at": utcnow()}})
    # cross-user learning: this strategy's rolling stats move for EVERYONE
    db[COLL_STRATEGIES].update_one(
        {"_id": attempt["strategy_id"]},
        {"$inc": {"stats.attempts": 1,
                  "stats.overturns": 1 if outcome == DETERMINATION_OVERTURNED else 0}})
    db[COLL_CASES].update_one(
        {"_id": case["_id"]},
        {"$set": {"stage": "won" if outcome == DETERMINATION_OVERTURNED else "responded"}})
    return attempt["strategy_id"]


# ----------------------------------------------------------------- endpoints
@app.get("/")
def home():
    return FileResponse("static/index.html")


@app.get("/api/meta")
def meta():
    return {"evidence_types": list(db[COLL_EVIDENCE].find()),
            "strategies": list(db[COLL_STRATEGIES].find())}


DATE_PATTERNS = [
    (r"([A-Z][a-z]+ \d{1,2}, \d{4})", "%B %d, %Y"),
    (r"(\d{1,2}/\d{1,2}/\d{4})", "%m/%d/%Y"),
    (r"(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
]


@app.post("/api/extract_pdf")
async def extract_pdf(file: UploadFile = File(...)):
    """Pull the letter text (and the denial date, when findable) out of a PDF."""
    from io import BytesIO

    from pypdf import PdfReader
    try:
        reader = PdfReader(BytesIO(await file.read()))
        text = "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    except Exception as e:
        raise HTTPException(422, f"could not read PDF: {e}")
    if not text:
        raise HTTPException(422, "no extractable text in this PDF (scanned image?)")
    detected = None
    for pat, fmt in DATE_PATTERNS:
        m = re.search(pat, text[:1500])
        if m:
            try:
                detected = datetime.strptime(m.group(1), fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
    return {"text": text[:12000], "pages": len(reader.pages), "detected_date": detected}


@app.post("/api/case")
def create_case(body: CaseIn):
    denial_date = (datetime.strptime(body.denial_date, "%Y-%m-%d")
                   if body.denial_date else utcnow())
    doc = {"created_at": utcnow(), "denial_text": body.denial_text,
           "denial_date": denial_date, "evidence_have": body.evidence_have,
           "stage": "intake", "deadlines": deadlines_for(denial_date)}
    cid = db[COLL_CASES].insert_one(doc).inserted_id
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


@app.post("/api/case/{cid}/draft")
def draft(cid: str):
    return {"case_id": cid, **do_draft(get_case(cid))}


@app.post("/api/case/{cid}/outcome")
def record_outcome(cid: str, body: OutcomeIn):
    if body.outcome not in (DETERMINATION_UPHELD, DETERMINATION_OVERTURNED):
        raise HTTPException(422, "outcome must be 'upheld' or 'overturned'")
    strategy_id = resolve_pending(get_case(cid), body.outcome)
    return {"case_id": cid, "recorded": body.outcome, "strategy_id": strategy_id}
