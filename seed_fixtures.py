#!/usr/bin/env python3
"""Seed fixture denial_profiles so Person B is unblocked during CSV load."""

import os
import sys

from pymongo import MongoClient, ReplaceOne

from fixtures import FIXTURE_PROFILES
from ingest import load_env
from schema import COLL_PROFILES


def main():
    load_env()
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB", "rebuttal")
    if not uri:
        sys.exit("MONGODB_URI missing")
    db = MongoClient(uri, serverSelectionTimeoutMS=15000)[db_name]
    coll = db[COLL_PROFILES]
    ops = [
        ReplaceOne({"source_ref": p["source_ref"]}, p, upsert=True)
        for p in FIXTURE_PROFILES
    ]
    coll.bulk_write(ops, ordered=False)
    print(f"denial_profiles fixtures upserted: {len(FIXTURE_PROFILES)}")
    print(f"denial_profiles count: {coll.count_documents({})}")


if __name__ == "__main__":
    main()
