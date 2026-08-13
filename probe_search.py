"""Go/no-go: which search mode works against denial_profiles?"""
import os

from dotenv import load_dotenv
from pymongo import MongoClient

from schema import COLL_PROFILES, EMBED_SOURCE, LEXICAL_INDEX, VECTOR_INDEX

load_dotenv()
db = MongoClient(os.environ["MONGODB_URI"])[os.environ.get("MONGODB_DB", "rebuttal")]
q = "CPAP device denied as not medically necessary for obstructive sleep apnea"

PROJECT = {"$project": {"_id": 0, "determination": 1,
                        "summary_text": {"$substrCP": [f"${EMBED_SOURCE}", 0, 80]}}}

print("--- vector (auto-embedded text query) ---")
try:
    hits = list(db[COLL_PROFILES].aggregate([
        {"$vectorSearch": {"index": VECTOR_INDEX, "path": EMBED_SOURCE,
                           "query": q, "exact": True, "limit": 3}}, PROJECT]))
    for h in hits:
        print("  ", h["determination"], h["summary_text"])
    print("VECTOR OK" if hits else "vector: no hits (index still building?)")
except Exception as e:
    print(f"vector FAILED: {e}")

print("--- lexical fallback ---")
try:
    hits = list(db[COLL_PROFILES].aggregate([
        {"$search": {"index": LEXICAL_INDEX,
                     "text": {"query": q, "path": EMBED_SOURCE}}},
        {"$limit": 3}, PROJECT]))
    for h in hits:
        print("  ", h["determination"], h["summary_text"])
    print("LEXICAL OK - set SEARCH_MODE=lexical if vector failed"
          if hits else "lexical: no hits (index still building?)")
except Exception as e:
    print(f"lexical FAILED: {e}")
