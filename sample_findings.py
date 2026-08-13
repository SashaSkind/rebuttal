#!/usr/bin/env python3
"""Print diagnosis/treatment density + sample findings for taxonomy (pass 1)."""

import os
import sys
from collections import Counter

from pymongo import MongoClient

from ingest import load_env
from schema import COLL_DECISIONS, SRC_OVERTURNED


def main():
    load_env()
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB", "rebuttal")
    if not uri:
        sys.exit("MONGODB_URI missing")
    coll = MongoClient(uri, serverSelectionTimeoutMS=15000)[db_name][COLL_DECISIONS]
    print("count", coll.estimated_document_count())
    print("\nTop DiagnosisCategory:")
    for row in coll.aggregate(
        [{"$group": {"_id": "$DiagnosisCategory", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 12}]
    ):
        print(f"  {row['n']:5d}  {row['_id']}")
    print("\nTop TreatmentCategory:")
    for row in coll.aggregate(
        [{"$group": {"_id": "$TreatmentCategory", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}, {"$limit": 12}]
    ):
        print(f"  {row['n']:5d}  {row['_id']}")

    sample = list(
        coll.find(
            {"Determination": SRC_OVERTURNED, "Findings": {"$exists": True, "$ne": ""}},
            {
                "ReferenceID": 1,
                "DiagnosisCategory": 1,
                "TreatmentCategory": 1,
                "Type": 1,
                "Determination": 1,
                "Findings": 1,
            },
        ).limit(25)
    )
    upheld = list(
        coll.find(
            {"Determination": {"$ne": SRC_OVERTURNED}, "Findings": {"$exists": True, "$ne": ""}},
            {
                "ReferenceID": 1,
                "DiagnosisCategory": 1,
                "TreatmentCategory": 1,
                "Type": 1,
                "Determination": 1,
                "Findings": 1,
            },
        ).limit(15)
    )
    print("\n===== SAMPLE FINDINGS =====")
    for d in sample + upheld:
        f = (d.get("Findings") or "")[:900]
        print("\n---", d.get("ReferenceID"), d.get("Determination"), d.get("Type"))
        print(d.get("DiagnosisCategory"), "/", d.get("TreatmentCategory"))
        print(f)


if __name__ == "__main__":
    main()
