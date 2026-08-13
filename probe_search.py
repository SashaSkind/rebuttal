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
    print("If the error mentions 'query'/'exact': try numCandidates:100 instead of exact.")
    print("If the error mentions the index/model: fall back to Atlas Search lexical ($search).")
