# Collections
COLL_DECISIONS = "imr_decisions"  # raw public data, unmodified
COLL_PROFILES = "denial_profiles"  # derived, searchable - the main index
COLL_STRATEGIES = "strategies"  # argument archetypes (dictionary, not stats)
COLL_EVIDENCE = "evidence_types"  # documentation archetypes (dictionary)
COLL_CASES = "cases"  # B owns
COLL_ATTEMPTS = "attempts"  # B owns

VECTOR_INDEX = "profiles_vector"
EMBED_FIELD = "summary_embedding"
EMBED_SOURCE = "summary_text"

DETERMINATION_OVERTURNED = "overturned"
DETERMINATION_UPHELD = "upheld"

# Source CSV / imr_decisions field names (verbatim from DMHC)
SRC_REF = "ReferenceID"
SRC_DIAGNOSIS_CAT = "DiagnosisCategory"
SRC_TREATMENT_CAT = "TreatmentCategory"
SRC_DETERMINATION = "Determination"
SRC_TYPE = "Type"  # Medical Necessity / Experimental/Investigational / Urgent Care
SRC_FINDINGS = "Findings"

# Source determination strings - map only in derived collections
SRC_UPHELD = "Upheld Decision of Health Plan"
SRC_OVERTURNED = "Overturned Decision of Health Plan"


def map_determination(source_value: str) -> str:
    if source_value == SRC_OVERTURNED:
        return DETERMINATION_OVERTURNED
    if source_value == SRC_UPHELD:
        return DETERMINATION_UPHELD
    raise ValueError(f"unknown Determination: {source_value!r}")


# ---- Person B additions (additive; the contract above is canonical) ----
LEXICAL_INDEX = "profiles_lexical"  # Atlas Search fallback index on summary_text
MIN_SAMPLE = 2  # min similar-case count for a strategy to rank; tune up with real data
# B-owned collections:
# cases:    {"_id", "created_at", "denial_text", "denial_date", "evidence_have": [key],
#            "stage": "intake"|"drafted"|"responded"|"won",
#            "deadlines": {"internal_appeal_due", "external_review_due"}}
# attempts: {"_id", "case_id": ObjectId, "strategy_id": <strategy key>, "stage",
#            "outcome": "pending"|"upheld"|"overturned", "recorded_at", "letter"}
