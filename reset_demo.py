"""Wipe live demo state (cases + attempts) for a clean first-contact demo run.
Does NOT touch the corpus, taxonomy, or indexes."""
import os

from dotenv import load_dotenv
from pymongo import MongoClient

from schema import COLL_ATTEMPTS, COLL_CASES

load_dotenv()
db = MongoClient(os.environ["MONGODB_URI"])[os.environ.get("MONGODB_DB", "rebuttal")]
print("cases removed:", db[COLL_CASES].delete_many({}).deleted_count)
print("attempts removed:", db[COLL_ATTEMPTS].delete_many({}).deleted_count)
