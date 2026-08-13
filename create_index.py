"""Create search indexes on denial_profiles.summary_text and poll until queryable.
Two indexes: the auto-embedding vector index (primary), and a lexical Atlas
Search index (fallback — set SEARCH_MODE=lexical if the vector one can't build).
Safe to re-run."""
import os
import time

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

from schema import COLL_PROFILES, EMBED_SOURCE, LEXICAL_INDEX, VECTOR_INDEX

load_dotenv()
db = MongoClient(os.environ["MONGODB_URI"])[os.environ.get("MONGODB_DB", "rebuttal")]
coll = db[COLL_PROFILES]

existing = [i["name"] for i in coll.list_search_indexes()]

if VECTOR_INDEX not in existing:
    try:
        coll.create_search_index(SearchIndexModel(
            name=VECTOR_INDEX, type="vectorSearch",
            definition={"fields": [
                {"type": "text", "path": EMBED_SOURCE, "model": "voyage-3-large"},
            ]},
        ))
        print(f"{VECTOR_INDEX}: creation requested (auto-embedding)")
    except Exception as e:
        print(f"{VECTOR_INDEX}: creation FAILED — {e}")
        print("-> plan on SEARCH_MODE=lexical")

if LEXICAL_INDEX not in existing:
    try:
        coll.create_search_index(SearchIndexModel(
            name=LEXICAL_INDEX, type="search",
            definition={"mappings": {"dynamic": True}},
        ))
        print(f"{LEXICAL_INDEX}: creation requested (lexical fallback)")
    except Exception as e:
        print(f"{LEXICAL_INDEX}: creation FAILED — {e}")

for _ in range(60):  # up to 5 minutes
    info = {i["name"]: i.get("queryable", False) for i in coll.list_search_indexes()}
    print("status:", info)
    if info.get(VECTOR_INDEX):
        print(f"READY — use SEARCH_MODE=vector (default)")
        break
    if info.get(LEXICAL_INDEX) and VECTOR_INDEX not in info:
        print(f"READY — vector index absent; set SEARCH_MODE=lexical in .env")
        break
    time.sleep(5)
else:
    print("Timed out waiting; check Atlas UI -> Search & Vector Search.")
