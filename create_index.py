"""Create the automated-embedding vector index on denial_profiles.search_text and
poll until queryable. Safe to re-run."""
import os
import time

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

from schema import DB_NAME, DENIAL_PROFILES, VECTOR_INDEX

load_dotenv()
db = MongoClient(os.environ["MONGODB_URI"])[DB_NAME]

existing = [i["name"] for i in db[DENIAL_PROFILES].list_search_indexes()]
if VECTOR_INDEX not in existing:
    db[DENIAL_PROFILES].create_search_index(SearchIndexModel(
        name=VECTOR_INDEX, type="vectorSearch",
        definition={"fields": [
            {"type": "text", "path": "search_text", "model": "voyage-3-large"},
        ]},
    ))
    print("index creation requested…")
while True:
    info = list(db[DENIAL_PROFILES].list_search_indexes(VECTOR_INDEX))
    if info and info[0].get("queryable"):
        print("READY")
        break
    print("waiting for index build…")
    time.sleep(5)
