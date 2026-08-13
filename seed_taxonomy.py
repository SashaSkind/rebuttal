#!/usr/bin/env python3
"""Upsert strategies + evidence_types dictionaries (no rolling stats)."""

import os
import sys

from pymongo import MongoClient, ReplaceOne

from ingest import load_env
from schema import COLL_EVIDENCE, COLL_STRATEGIES
from taxonomy import EVIDENCE_TYPES, STRATEGIES


def main():
    load_env()
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB", "rebuttal")
    if not uri:
        sys.exit("MONGODB_URI missing")
    db = MongoClient(uri, serverSelectionTimeoutMS=15000)[db_name]
    for coll_name, docs in ((COLL_STRATEGIES, STRATEGIES), (COLL_EVIDENCE, EVIDENCE_TYPES)):
        ops = [ReplaceOne({"key": d["key"]}, d, upsert=True) for d in docs]
        db[coll_name].bulk_write(ops, ordered=False)
        print(f"{coll_name}: {len(docs)} keys, count={db[coll_name].count_documents({})}")


if __name__ == "__main__":
    main()
