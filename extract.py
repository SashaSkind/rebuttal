#!/usr/bin/env python3
"""Pass 2: classify imr_decisions into denial_profiles against frozen taxonomy.

Requires FIREWORKS_API_KEY. Checkpoints to data/extract_checkpoint.jsonl
Concentrate in FOCUS_DIAGNOSIS. Do not run until taxonomy is eyeballed.
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from pymongo import MongoClient, ReplaceOne

from ingest import load_env
from schema import (
    COLL_DECISIONS,
    COLL_PROFILES,
    EMBED_SOURCE,
    map_determination,
)
from taxonomy import EVIDENCE_KEYS, FOCUS_DIAGNOSIS, STRATEGY_KEYS

CHECKPOINT = os.path.join("data", "extract_checkpoint.jsonl")
TARGET_N = 2000
WORKERS = 16
MODEL = os.environ.get("FIREWORKS_MODEL", "accounts/fireworks/models/gpt-oss-20b")


def client_db():
    load_env()
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        sys.exit("MONGODB_URI missing")
    return MongoClient(uri, serverSelectionTimeoutMS=15000)[
        os.environ.get("MONGODB_DB", "rebuttal")
    ]


def loaded_refs():
    done = set()
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("source_ref") and not rec.get("error"):
                    done.add(rec["source_ref"])
    return done


def pick_rows(coll, need, skip_refs):
    q = {
        "DiagnosisCategory": {"$in": FOCUS_DIAGNOSIS},
        "Findings": {"$exists": True, "$nin": [None, ""]},
        "ReferenceID": {"$nin": list(skip_refs)[:10000] or ["__none__"]},
    }
    # Prefer overturned by sorting Determination desc is unreliable; sample both.
    rows = list(coll.find(q).limit(need * 2))
    out = []
    for r in rows:
        if r["ReferenceID"] in skip_refs:
            continue
        out.append(r)
        if len(out) >= need:
            break
    return out


def classify_one(row, api_key):
    import ssl
    import urllib.request

    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = None

    findings = (row.get("Findings") or "")[:2000]
    payload = json.dumps(
        {
            "model": MODEL,
            "max_tokens": 1200,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return one JSON object. Keys: strategy_keys, evidence_keys, "
                        "reasoning_pattern, summary_text. "
                        f"strategy_keys: 1-3 from {STRATEGY_KEYS}. "
                        f"evidence_keys: 1-3 from {EVIDENCE_KEYS}. "
                        "reasoning_pattern: one sentence. "
                        "summary_text: write like a denial letter — condition, requested "
                        "service, plan's stated reason. Never mention overturned, upheld, "
                        "the reviewer, or the IMR result. Never invent slugs."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "DiagnosisCategory": row.get("DiagnosisCategory"),
                            "TreatmentCategory": row.get("TreatmentCategory"),
                            "Type": row.get("Type"),
                            "Findings": findings,
                        }
                    ),
                },
            ],
        }
    ).encode()
    last_err = None
    for _ in range(2):
        try:
            req = urllib.request.Request(
                "https://api.fireworks.ai/inference/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                body = json.loads(resp.read().decode())
            text = (body["choices"][0]["message"].get("content") or "").strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:]
            parsed = json.loads(text)
            sk = [k for k in parsed.get("strategy_keys", []) if k in STRATEGY_KEYS]
            ek = [k for k in parsed.get("evidence_keys", []) if k in EVIDENCE_KEYS]
            summary = (parsed.get("summary_text") or "").strip()
            reason = (parsed.get("reasoning_pattern") or "").strip()
            if not summary or not sk:
                raise ValueError("empty classification")
            return {
                "source_ref": row["ReferenceID"],
                "determination": map_determination(row["Determination"]),
                "segment": {
                    "diagnosis_category": row.get("DiagnosisCategory") or "",
                    "treatment_category": row.get("TreatmentCategory") or "",
                    "denial_type": row.get("Type") or "",
                },
                "service_type": row.get("TreatmentCategory") or "",
                "reasoning_pattern": reason,
                "strategy_keys": sk,
                "evidence_keys": ek,
                EMBED_SOURCE: summary,
            }
        except Exception as e:
            last_err = e
            time.sleep(0.5)
    return {"source_ref": row["ReferenceID"], "error": str(last_err)}


def main():
    load_env()
    api_key = os.environ.get("FIREWORKS_API_KEY")
    if not api_key:
        sys.exit("FIREWORKS_API_KEY missing — taxonomy is seeded; pass 2 waits on this key")
    db = client_db()
    done = loaded_refs()
    need = TARGET_N - len(done)
    print(f"checkpoint {len(done)}; need {need} more")
    if need <= 0:
        print("done")
        return
    rows = pick_rows(db[COLL_DECISIONS], need, done)
    print(f"queued {len(rows)} rows")
    os.makedirs("data", exist_ok=True)
    ok_ops = []
    n_ok = n_fail = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(classify_one, r, api_key): r for r in rows}
        for i, fut in enumerate(as_completed(futs), 1):
            rec = fut.result()
            with open(CHECKPOINT, "a") as f:
                f.write(json.dumps(rec) + "\n")
            if rec.get("error"):
                n_fail += 1
            else:
                n_ok += 1
                ok_ops.append(ReplaceOne({"source_ref": rec["source_ref"]}, rec, upsert=True))
            if i % 25 == 0:
                print(f"  {i}/{len(rows)} ok={n_ok} fail={n_fail}")
            if len(ok_ops) >= 50:
                db[COLL_PROFILES].bulk_write(ok_ops, ordered=False)
                ok_ops = []
    if ok_ops:
        db[COLL_PROFILES].bulk_write(ok_ops, ordered=False)
    print(f"finished ok={n_ok} fail={n_fail} profiles={db[COLL_PROFILES].count_documents({})}")


if __name__ == "__main__":
    main()
