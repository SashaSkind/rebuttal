"""Seed the strategies / evidence_types dictionaries for the keys used in
denial_profiles. Idempotent upserts; safe to re-run. Names/descriptions power
the UI and the $lookup display - the stats live on the profile aggregation."""
import os

from dotenv import load_dotenv
from pymongo import MongoClient

from schema import COLL_EVIDENCE, COLL_STRATEGIES

load_dotenv()
db = MongoClient(os.environ["MONGODB_URI"])[os.environ.get("MONGODB_DB", "rebuttal")]

STRATEGIES = [
    {"_id": "standard_of_care_guideline", "name": "Standard of care per named guideline",
     "description": "Establish the requested service is standard of care by citing a named clinical guideline (NCCN, AASLD, AASM, ACC/AHA...).",
     "example_phrasing": "Under the applicable specialty guideline, the requested service is standard of care for my diagnosis."},
    {"_id": "failed_preferred_alternative", "name": "Plan-preferred alternative already failed",
     "description": "Document that the plan-preferred alternative was tried and failed, or is contraindicated for this patient.",
     "example_phrasing": "The plan-preferred therapy was tried and failed, as documented in my treatment records."},
    {"_id": "failed_lower_level_of_care", "name": "Lower level of care already failed",
     "description": "Show the less-intensive covered option was already attempted and was clinically insufficient.",
     "example_phrasing": "The lower level of care the plan proposes was already attempted and failed."},
    {"_id": "policy_criteria_met", "name": "Plan's own criteria are met",
     "description": "Quote the plan's published coverage criteria and show each element is satisfied or was misapplied.",
     "example_phrasing": "Under the plan's own published medical policy, each coverage criterion is met."},
    {"_id": "peer_reviewed_literature", "name": "Peer-reviewed literature support",
     "description": "Cite specific published studies demonstrating efficacy and safety for this indication.",
     "example_phrasing": "Peer-reviewed studies, including controlled trials, support this treatment for my indication."},
    {"_id": "safety_risk_if_denied", "name": "Denial creates a documented safety risk",
     "description": "Show the denial exposes the patient to concrete, documented harm.",
     "example_phrasing": "Denying this service exposes me to a documented and avoidable safety risk."},
    {"_id": "acute_change_in_status", "name": "Acute change in clinical status",
     "description": "A documented new or worsening finding justifies the requested service now.",
     "example_phrasing": "My clinical status has acutely changed, as documented, warranting the requested service."},
    {"_id": "functional_limitation_documented", "name": "Documented functional limitation",
     "description": "Objective findings document a functional limitation the requested service addresses.",
     "example_phrasing": "My documented functional limitations require the requested device or service."},
    {"_id": "assessment_supports_intensity", "name": "Assessment supports requested intensity",
     "description": "A recent standardized assessment supports the requested treatment intensity.",
     "example_phrasing": "The most recent standardized assessment supports the requested intensity of treatment."},
]

EVIDENCE = [
    {"_id": "treating_physician_attestation", "name": "Treating physician attestation",
     "description": "Letter from the treating physician tying patient specifics to the requested service."},
    {"_id": "named_clinical_guideline", "name": "Named guideline excerpt",
     "description": "The relevant page of NCCN/AASLD/AASM/ACC-AHA or similar."},
    {"_id": "published_studies", "name": "Published studies",
     "description": "Peer-reviewed journal articles supporting the requested service."},
    {"_id": "physical_exam_findings", "name": "Physical exam findings",
     "description": "Documented exam findings supporting severity or limitation."},
    {"_id": "hospitalization_records", "name": "Hospitalization records",
     "description": "Records of recent admissions or emergency care."},
    {"_id": "lab_and_glucose_logs", "name": "Lab results / glucose logs",
     "description": "Objective lab values or monitoring logs."},
    {"_id": "lab_and_imaging", "name": "Lab and imaging results",
     "description": "Combined laboratory and imaging documentation."},
    {"_id": "pharmacy_fill_history", "name": "Pharmacy fill history",
     "description": "Fill records showing which drugs were actually tried."},
    {"_id": "neurologic_exam", "name": "Neurologic exam",
     "description": "Documented neurological examination findings."},
    {"_id": "bmi_and_comorbidity_chart", "name": "BMI and comorbidity chart",
     "description": "Charted BMI history and comorbid conditions."},
    {"_id": "cath_report", "name": "Catheterization report",
     "description": "Cardiac catheterization findings."},
    {"_id": "stress_test_results", "name": "Stress test results",
     "description": "Exercise or pharmacologic stress test results."},
    {"_id": "sleep_study", "name": "Sleep study",
     "description": "Polysomnography or home sleep apnea test results."},
    {"_id": "spirometry_and_exacerbation_history", "name": "Spirometry / exacerbation history",
     "description": "Pulmonary function tests and exacerbation records."},
    {"_id": "behavioral_assessment", "name": "Behavioral assessment",
     "description": "Recent standardized behavioral assessment results."},
    {"_id": "procedure_response_notes", "name": "Procedure response notes",
     "description": "Documented response to prior procedures or injections."},
]


def run():
    for s in STRATEGIES:
        db[COLL_STRATEGIES].update_one({"_id": s["_id"]}, {"$set": s}, upsert=True)
    for e in EVIDENCE:
        db[COLL_EVIDENCE].update_one({"_id": e["_id"]}, {"$set": e}, upsert=True)
    print(f"strategies={db[COLL_STRATEGIES].count_documents({})} "
          f"evidence={db[COLL_EVIDENCE].count_documents({})}")


if __name__ == "__main__":
    run()
