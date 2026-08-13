#!/usr/bin/env python3
"""Load unmodified DMHC IMR CSV into imr_decisions; seed fixture profiles."""

import csv
import os
import sys
import urllib.request
from collections import Counter

from pymongo import MongoClient, ReplaceOne

from fixtures import FIXTURE_PROFILES
from schema import COLL_DECISIONS, COLL_PROFILES

OFFICIAL_CSV = (
    "https://data.chhs.ca.gov/dataset/b79b3447-4c10-4ae6-84e2-1076f83bb24e/"
    "resource/3340c5d7-4054-4d03-90e0-5f44290ed095/download/"
    "independent-medical-review-imr-determinations-trends.csv"
)
LOCAL_CSV = os.path.join("data", "imr.csv")
BATCH = 1000
# CKAN dump adds _id; official CSV does not. Never persist extra fields.
DROP_FIELDS = {"_id"}


def load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def download_rows():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(LOCAL_CSV) or os.path.getsize(LOCAL_CSV) < 1_000_000:
        print(f"Downloading {OFFICIAL_CSV} ...")
        urllib.request.urlretrieve(OFFICIAL_CSV, LOCAL_CSV)
    print(f"Reading {LOCAL_CSV} ({os.path.getsize(LOCAL_CSV)} bytes)")
    with open(LOCAL_CSV, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [h for h in (reader.fieldnames or []) if h not in DROP_FIELDS]
        rows = list(reader)
    print(f"CSV headers: {headers}")
    print(f"Row count: {len(rows)}")
    return headers, rows


def main():
    load_env()
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB", "rebuttal")
    if not uri:
        sys.exit("MONGODB_URI missing")

    headers, rows = download_rows()
    dets = Counter(r.get("Determination", "") for r in rows)
    print("Determination distribution:")
    for k, v in dets.most_common():
        print(f"  {v:6d}  {k!r}")

    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    db = client[db_name]
    try:
        client.admin.command("ping")
        print(f"Connected. db={db_name} ping=ok")
    except Exception as e:
        print(f"Auth/connect failed as configured user: {e}")
        sys.exit(1)

    coll = db[COLL_DECISIONS]
    ops = []
    n = 0
    for r in rows:
        doc = {h: r.get(h, "") for h in headers}
        ref = doc.get("ReferenceID")
        if not ref:
            continue
        ops.append(ReplaceOne({"ReferenceID": ref}, doc, upsert=True))
        if len(ops) >= BATCH:
            coll.bulk_write(ops, ordered=False)
            n += len(ops)
            print(f"  wrote {n} imr_decisions ...")
            ops = []
    if ops:
        coll.bulk_write(ops, ordered=False)
        n += len(ops)
    print(f"imr_decisions upserted: {n}")
    print(f"imr_decisions count: {coll.count_documents({})}")

    pcoll = db[COLL_PROFILES]
    pops = [
        ReplaceOne({"source_ref": p["source_ref"]}, p, upsert=True)
        for p in FIXTURE_PROFILES
    ]
    pcoll.bulk_write(pops, ordered=False)
    print(f"denial_profiles fixtures upserted: {len(FIXTURE_PROFILES)}")
    print(f"denial_profiles count: {pcoll.count_documents({})}")


if __name__ == "__main__":
    main()
