"""THE acceptance test: same denial letter, different ranking after a recorded loss.
Run with the server up:  uvicorn main:app --port 8000"""
import requests

BASE = "http://localhost:8000"
LETTER = open("demo/denial_letter.txt").read()

case = requests.post(f"{BASE}/api/case", json={
    "denial_text": LETTER, "denial_date": "2026-07-20",
    "evidence_have": ["sleep_study"]}).json()
cid = case["case_id"]

r1 = requests.post(f"{BASE}/api/case/{cid}/analyze").json()
assert r1["strategies"], "no ranked strategies — is a search index queryable?"
ids1 = [s["strategy_id"] for s in r1["strategies"]]
top1 = ids1[0]

d = requests.post(f"{BASE}/api/case/{cid}/draft").json()
assert d["strategy"]["strategy_id"] == top1

requests.post(f"{BASE}/api/case/{cid}/outcome", json={"outcome": "upheld"})

r2 = requests.post(f"{BASE}/api/case/{cid}/analyze").json()
ids2 = [s["strategy_id"] for s in r2["strategies"]]

assert top1 not in ids2, f"FAIL: excluded strategy {top1} still ranked"
assert ids1 != ids2, "FAIL: ranking unchanged after recorded loss"
assert top1 in [e["strategy_id"] for e in r2["excluded"]], "FAIL: loss not surfaced in excluded list"

d2 = requests.post(f"{BASE}/api/case/{cid}/draft").json()
assert d2["strategy"]["strategy_id"] != top1, "FAIL: redrafted with the failed strategy"

print(f"PASS: exclusion works — {top1} -> {ids2[0]}")
