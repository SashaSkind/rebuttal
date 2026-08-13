"""Schema contract for Rebuttal. FROZEN — nobody edits field/collection names.
(Exception: MIN_SAMPLE is a tuning constant, not contract.)

Person A writes denial_profiles / strategies / evidence_types via ingest.py.
Person B reads them in main.py and owns cases / attempts.
imr_decisions holds raw DMHC rows VERBATIM — we never modify them; derived data
lives in separate collections referencing source rows by ID (license terms).
"""

DB_NAME = "nocoldstart"

# ---- collection names ----
IMR_DECISIONS = "imr_decisions"      # raw DMHC rows, verbatim
DENIAL_PROFILES = "denial_profiles"  # derived; THE collection we vector-search
STRATEGIES = "strategies"            # argument archetype catalog + rolling stats
EVIDENCE_TYPES = "evidence_types"    # documentation category catalog
CASES = "cases"                      # live user state (B)
ATTEMPTS = "attempts"                # per-user strategy history (B) — the memory

VECTOR_INDEX = "profiles_vector"     # auto-embedding index on denial_profiles.search_text

# ---- raw-row field names (if the real CSV header differs, fix THESE THREE LINES ONLY) ----
RAW_REF_FIELD = "ReferenceID"
RAW_DETERMINATION_FIELD = "Determination"   # e.g. "Overturned Decision of Health Plan"
RAW_FINDINGS_FIELD = "Findings"

# ---- normalized outcome values on denial_profiles.outcome ----
OUTCOME_OVERTURNED = "overturned"   # RAW determination startswith "Overturned"
OUTCOME_UPHELD = "upheld"

MIN_SAMPLE = 2   # min similar-case count for a strategy to rank; raise to 3 after real-data swap

# ---- denial_profiles document shape ----
# {
#   "_id": ObjectId,
#   "source_id": str,          # == imr_decisions[RAW_REF_FIELD] of the source row
#   "search_text": str,        # neutral 40-90 word summary of the DENIAL SITUATION.
#                              #   Auto-embedded by the vector index. MUST NOT mention
#                              #   the outcome (would bias retrieval).
#   "diagnosis_category": str, # e.g. "Cancer"
#   "treatment_category": str,
#   "denial_type": str,        # "Medical Necessity" | "Experimental/Investigational" | "Urgent Care"
#   "outcome": str,            # OUTCOME_OVERTURNED | OUTCOME_UPHELD (from raw Determination)
#   "strategy_ids": [str],     # 0-3 slugs from STRATEGY_CATALOG the reviewer's reasoning relied on
#   "evidence_present": [str], # slugs from EVIDENCE_CATALOG the findings credit
#   "is_fixture": bool,        # True only on hand-written fixtures; deleted at the swap
# }
#
# cases:    {"_id", "created_at", "denial_text", "denial_date", "evidence_have": [slug],
#            "stage": "intake"|"drafted"|"responded"|"won", "deadlines": {
#              "internal_appeal_due": datetime, "external_review_due": datetime}}
# attempts: {"_id", "case_id": ObjectId, "strategy_id": slug, "stage": str,
#            "outcome": "pending"|"upheld"|"overturned", "recorded_at": datetime,
#            "letter": str}

# ---- CLOSED strategy vocabulary. A's extraction classifies into these slugs. ----
STRATEGY_CATALOG = [
    {"_id": "cite-clinical-guideline", "name": "Standard of care per named guideline",
     "description": "Establish the requested service is standard of care by citing a named clinical guideline (NCCN, ASCO, AAP, ACR...).",
     "example_phrasing": "NCCN Guidelines list the requested therapy as an appropriate treatment for this diagnosis.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "failed-alternatives", "name": "Plan-preferred alternative already failed",
     "description": "Document that the insurer's preferred alternative was tried and failed, or is contraindicated for this patient.",
     "example_phrasing": "The plan-preferred therapy was administered for 12 weeks and failed, as documented by the treating physician.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "peer-reviewed-evidence", "name": "Peer-reviewed literature support",
     "description": "Cite specific published studies demonstrating efficacy and safety of the requested service for this indication.",
     "example_phrasing": "Three peer-reviewed studies, including a randomized trial, support efficacy for this indication.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "treating-physician-rationale", "name": "Treating specialist's medical-necessity rationale",
     "description": "A detailed letter from the treating physician tying this patient's specific clinical facts to the requested service.",
     "example_phrasing": "My treating specialist's attached letter details why this therapy is medically necessary for my specific presentation.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "plan-criteria-met", "name": "Plan's own criteria are met",
     "description": "Quote the insurer's published coverage criteria and show each element is satisfied or was misapplied.",
     "example_phrasing": "Under the plan's own medical policy, the published criteria for coverage are met, as shown below.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "fda-approved-indication", "name": "FDA-approved / compendia-supported use",
     "description": "The service, device, or drug is FDA-approved or listed in recognized compendia for exactly this indication.",
     "example_phrasing": "The requested treatment is FDA-approved for this indication and cannot be deemed experimental.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "continuity-of-care", "name": "Interrupting effective treatment causes harm",
     "description": "An established treatment is working; interruption risks regression or deterioration.",
     "example_phrasing": "Discontinuing a therapy under which I have documentably improved would risk serious regression.",
     "stats": {"attempts": 0, "overturns": 0}},
    {"_id": "urgent-risk", "name": "Delay poses imminent risk",
     "description": "Physician attests that delay poses imminent or irreversible harm, triggering expedited review.",
     "example_phrasing": "My physician attests that any delay in treatment poses an imminent threat to my health.",
     "stats": {"attempts": 0, "overturns": 0}},
]

EVIDENCE_CATALOG = [
    {"_id": "physician-letter", "name": "Letter of medical necessity",
     "description": "From the treating physician, tying patient specifics to the requested service."},
    {"_id": "clinical-guideline-citation", "name": "Named guideline excerpt",
     "description": "The relevant page of NCCN/ASCO/AAP/ACR or similar."},
    {"_id": "peer-reviewed-studies", "name": "Peer-reviewed studies",
     "description": "Published journal articles supporting the requested service."},
    {"_id": "prior-treatment-records", "name": "Prior treatment records",
     "description": "Records showing alternatives tried, duration, and outcomes."},
    {"_id": "imaging-test-results", "name": "Imaging / test results",
     "description": "Objective results supporting diagnosis and severity."},
    {"_id": "specialist-second-opinion", "name": "Specialist second opinion",
     "description": "Independent specialist concurrence with the treatment plan."},
    {"_id": "plan-policy-excerpt", "name": "Insurer's own policy excerpt",
     "description": "The plan's published coverage criteria for the service."},
    {"_id": "fda-compendia-support", "name": "FDA label / compendia listing",
     "description": "FDA approval or recognized compendium listing for this indication."},
]
