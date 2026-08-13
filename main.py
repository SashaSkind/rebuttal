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
from pydantic import BaseModel
from pymongo import MongoClient

from schema import (ATTEMPTS, CASES, DB_NAME, DENIAL_PROFILES, EVIDENCE_TYPES,
                    IMR_DECISIONS, MIN_SAMPLE, OUTCOME_OVERTURNED, OUTCOME_UPHELD,
                    RAW_DETERMINATION_FIELD, RAW_FINDINGS_FIELD, RAW_REF_FIELD,
                    STRATEGIES, VECTOR_INDEX)

load_dotenv()
client = MongoClient(os.environ["MONGODB_URI"])
db = client[DB_NAME]

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


# ---------------------------------------------------------------- the product
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
                {"$match": {"strategy_ids": {"$nin": failed}}},   # <-- the exclusion
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


# ------------------------------------------------------------------ drafting
def compose_letter(case: dict, strategy: dict, missing) -> str:
    """Deterministic letter composer — every sentence is driven by stored state:
    the top non-excluded strategy, its live track record, the user's evidence
    list, and the computed deadline. (LLM drafting was cut for time.)"""
    evidence_names = {e["_id"]: e["name"] for e in db[EVIDENCE_TYPES].find()}
    have = [evidence_names.get(s, s) for s in case.get("evidence_have", [])]
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
        f"The central basis of this appeal: {strategy['example_phrasing']} "
        "The clinical record accompanying this appeal supports this argument in my case.",
        (f"In {strategy['n']} comparable cases reviewed under California's Independent "
         f"Medical Review program, this argument prevailed in {strategy['overturns']} — "
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


def do_draft(case: dict) -> dict:
    ranked = rank_strategies(case)
    if not ranked["strategies"]:
        raise HTTPException(409, "no strategies left — every known argument has been excluded")
    top = ranked["strategies"][0]
    letter = compose_letter(case, top, ranked["missing_evidence"])
    db[ATTEMPTS].insert_one({"case_id": case["_id"], "strategy_id": top["strategy_id"],
                             "stage": case["stage"], "outcome": "pending",
                             "recorded_at": utcnow(), "letter": letter})
    db[CASES].update_one({"_id": case["_id"]}, {"$set": {"stage": "drafted"}})
    return {"strategy": top, "letter": letter}


def resolve_pending(case: dict, outcome: str) -> str:
    """Record how the latest filed appeal landed. The write that makes memory."""
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


# ----------------------------------------------------------------- endpoints
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


@app.post("/api/case/{cid}/draft")
def draft(cid: str):
    return {"case_id": cid, **do_draft(get_case(cid))}


@app.post("/api/case/{cid}/outcome")
def record_outcome(cid: str, body: OutcomeIn):
    if body.outcome not in (OUTCOME_UPHELD, OUTCOME_OVERTURNED):
        raise HTTPException(422, "outcome must be 'upheld' or 'overturned'")
    strategy_id = resolve_pending(get_case(cid), body.outcome)
    return {"case_id": cid, "recorded": body.outcome, "strategy_id": strategy_id}
