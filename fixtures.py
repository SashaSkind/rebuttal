"""Seed fixture data so B can build the whole pipeline before A's extraction lands.
Idempotent: deletes previous fixtures first. Everything fixture-made carries
is_fixture=True so the swap can delete it in one statement."""
import os

from dotenv import load_dotenv
from pymongo import MongoClient

from schema import (ATTEMPTS, CASES, DB_NAME, DENIAL_PROFILES, EVIDENCE_CATALOG,
                    EVIDENCE_TYPES, IMR_DECISIONS, RAW_DETERMINATION_FIELD,
                    RAW_FINDINGS_FIELD, RAW_REF_FIELD, STRATEGIES, STRATEGY_CATALOG)

load_dotenv()
db = MongoClient(os.environ["MONGODB_URI"])[DB_NAME]

OT, UP = "overturned", "upheld"
DET = {OT: "Overturned Decision of Health Plan", UP: "Upheld Decision of Health Plan"}

# (source_id, outcome, diagnosis, treatment, denial_type, strategies, evidence, search_text, findings)
ROWS = [
    ("FX-001", OT, "Cancer", "Cancer Care", "Experimental/Investigational",
     ["cite-clinical-guideline", "treating-physician-rationale"],
     ["clinical-guideline-citation", "physician-letter"],
     "Health plan denied proton beam radiation therapy for localized prostate cancer as "
     "experimental and investigational, stating IMRT is the covered alternative. The treating "
     "radiation oncologist recommends proton therapy citing reduced rectal and bladder toxicity "
     "for this patient's anatomy, and notes NCCN guidelines include it as an appropriate option.",
     "The physician reviewer found proton beam therapy a clinically appropriate option per NCCN "
     "guidelines and found the treating physician's toxicity rationale persuasive."),
    ("FX-002", OT, "Cancer", "Cancer Care", "Medical Necessity",
     ["cite-clinical-guideline", "continuity-of-care"],
     ["clinical-guideline-citation", "prior-treatment-records"],
     "Insurer denied continued proton beam therapy for prostate cancer, calling it not medically "
     "necessary versus conventional radiation. The patient had already begun a proton course; the "
     "oncologist documented that switching modalities mid-treatment risks overlapping toxicity and "
     "cited guideline support for completing the planned course.",
     "The reviewer concluded interrupting an in-progress radiation course was not clinically "
     "supportable and that guideline citations supported completing proton therapy."),
    ("FX-003", UP, "Cancer", "Cancer Care", "Experimental/Investigational",
     ["peer-reviewed-evidence"], [],
     "Plan denied proton beam therapy for early-stage prostate cancer as experimental, offering "
     "IMRT instead. The appeal cited general internet articles about proton therapy without "
     "patient-specific clinical documentation or guideline citations.",
     "The reviewer found no patient-specific clinical rationale and determined IMRT was an "
     "equally effective covered alternative for this presentation."),
    ("FX-004", OT, "Cancer", "Cancer Care", "Experimental/Investigational",
     ["cite-clinical-guideline", "failed-alternatives"],
     ["clinical-guideline-citation", "prior-treatment-records", "physician-letter"],
     "Plan denied proton beam therapy for prostate cancer as experimental. The patient had prior "
     "pelvic radiation, and the oncologist documented that the plan-preferred IMRT was "
     "contraindicated given cumulative dose to adjacent tissue, citing NCCN inclusion of proton "
     "therapy for re-irradiation scenarios.",
     "The reviewer found the plan-preferred alternative contraindicated due to prior radiation "
     "exposure and cited guideline support for proton therapy in this scenario."),
    ("FX-005", OT, "Cancer", "Cancer Care", "Medical Necessity",
     ["failed-alternatives", "treating-physician-rationale"],
     ["prior-treatment-records", "physician-letter"],
     "Insurer denied proton therapy for recurrent prostate cancer after previous external beam "
     "radiation had failed. The treating oncologist detailed why repeat conventional radiation "
     "carried unacceptable toxicity for this patient and why proton therapy's dose profile was "
     "medically necessary.",
     "The reviewer credited the documented failure of prior conventional radiation and the "
     "treating oncologist's patient-specific toxicity analysis."),
    ("FX-006", UP, "Cancer", "Cancer Care", "Experimental/Investigational",
     ["treating-physician-rationale"], ["physician-letter"],
     "Plan denied proton beam therapy for low-risk prostate cancer as experimental. The physician "
     "letter asserted a preference for proton therapy but did not document why IMRT would be "
     "inadequate for this specific presentation.",
     "The reviewer found the physician letter conclusory, lacking patient-specific evidence that "
     "the standard covered modality was inadequate."),
    ("FX-007", OT, "Cancer", "Cancer Care", "Experimental/Investigational",
     ["cite-clinical-guideline", "peer-reviewed-evidence"],
     ["clinical-guideline-citation", "peer-reviewed-studies"],
     "Health plan denied proton beam radiation for prostate cancer as investigational. The appeal "
     "cited NCCN guideline inclusion and two randomized-trial publications on dosimetric "
     "advantage and reduced genitourinary toxicity for the requested indication.",
     "The reviewer found guideline inclusion and randomized-trial evidence sufficient to "
     "establish the therapy as non-investigational for this indication."),
    ("FX-008", UP, "Cancer", "Cancer Care", "Urgent Care",
     ["urgent-risk", "continuity-of-care"], ["physician-letter"],
     "Expedited review was requested to begin proton beam therapy for prostate cancer without "
     "delay, arguing that any treatment gap would jeopardize outcomes. The plan denied the "
     "service as experimental and disputed the urgency.",
     "The reviewer found no clinical evidence that a short delay would alter outcomes and upheld "
     "the plan's determination on the underlying service."),
    ("FX-009", OT, "Orthopedic/Musculoskeletal", "Surgery", "Medical Necessity",
     ["failed-alternatives", "treating-physician-rationale"],
     ["prior-treatment-records", "imaging-test-results", "physician-letter"],
     "Plan denied lumbar spinal fusion as not medically necessary. The patient completed twelve "
     "months of physical therapy and epidural injections without relief; the surgeon's letter "
     "documented progressive neurological symptoms and correlating MRI findings of instability.",
     "The reviewer credited exhausted conservative care and imaging-confirmed instability, "
     "finding surgical intervention medically necessary."),
    ("FX-010", OT, "Orthopedic/Musculoskeletal", "Surgery", "Medical Necessity",
     ["plan-criteria-met", "failed-alternatives"],
     ["plan-policy-excerpt", "prior-treatment-records"],
     "Insurer denied cervical fusion surgery. The appeal quoted the plan's own published medical "
     "policy criteria for surgical intervention and documented point by point that conservative "
     "care had been exhausted and each criterion was satisfied.",
     "The reviewer found the plan's own coverage criteria were met on the submitted record and "
     "the denial inconsistent with the plan's published policy."),
    ("FX-011", UP, "Orthopedic/Musculoskeletal", "Surgery", "Medical Necessity",
     ["treating-physician-rationale"], ["physician-letter"],
     "Plan denied lumbar fusion for chronic low back pain. The surgeon recommended surgery, but "
     "records showed only six weeks of conservative treatment attempted before the surgical "
     "request.",
     "The reviewer found conservative treatment had not been adequately attempted and upheld "
     "the denial as consistent with standard practice."),
    ("FX-012", OT, "Orthopedic/Musculoskeletal", "Surgery", "Experimental/Investigational",
     ["cite-clinical-guideline", "fda-approved-indication"],
     ["clinical-guideline-citation", "imaging-test-results"],
     "Insurer denied artificial disc replacement as experimental. The appeal cited specialty "
     "society guidelines recognizing the procedure for single-level disease, the device's FDA "
     "approval for exactly this indication, and MRI findings matching the labeled indication.",
     "The reviewer noted FDA approval and specialty guideline recognition, concluding the "
     "procedure is not experimental for this indication."),
    ("FX-013", UP, "Orthopedic/Musculoskeletal", "Surgery", "Medical Necessity",
     ["peer-reviewed-evidence", "fda-approved-indication"], ["peer-reviewed-studies"],
     "Plan denied a spinal cord stimulator trial for chronic pain. The appeal cited journal "
     "articles on stimulator efficacy and the device's FDA approval, but did not address the "
     "plan's requirement of a documented psychological evaluation.",
     "The reviewer found required evaluation criteria unmet regardless of the cited literature "
     "and upheld the denial."),
    ("FX-014", UP, "Orthopedic/Musculoskeletal", "Surgery", "Medical Necessity",
     ["plan-criteria-met", "cite-clinical-guideline"], ["plan-policy-excerpt"],
     "Insurer denied lumbar fusion. The appeal argued the plan's criteria were met and cited "
     "surgical guidelines, but imaging did not document the spinal instability that both the "
     "policy and the cited guidelines require.",
     "The reviewer found the objective imaging findings did not satisfy the policy's "
     "instability requirement and upheld the denial."),
    ("FX-015", OT, "Autism Spectrum", "Behavioral Health", "Medical Necessity",
     ["treating-physician-rationale", "continuity-of-care"],
     ["physician-letter", "prior-treatment-records"],
     "Plan reduced approved ABA therapy from thirty to ten weekly hours for a child with autism. "
     "The treating psychologist documented measurable gains under the current intensity and a "
     "clinically significant regression risk if hours were reduced mid-program.",
     "The reviewer credited documented progress under the prescribed intensity and the "
     "regression risk of reduction, restoring the requested hours."),
    ("FX-016", OT, "Autism Spectrum", "Behavioral Health", "Medical Necessity",
     ["plan-criteria-met", "treating-physician-rationale"],
     ["plan-policy-excerpt", "physician-letter"],
     "Insurer denied continued ABA therapy hours as not medically necessary. The appeal quoted "
     "the plan's behavioral health medical policy and showed each coverage criterion was met, "
     "supported by the treating clinician's assessment-based treatment plan.",
     "The reviewer found the plan's own behavioral health criteria satisfied on the record and "
     "the denial unsupported."),
    ("FX-017", OT, "Autism Spectrum", "Behavioral Health", "Medical Necessity",
     ["cite-clinical-guideline", "continuity-of-care"],
     ["clinical-guideline-citation", "physician-letter"],
     "Plan denied the requested ABA therapy intensity for a child with autism. The appeal cited "
     "professional society treatment guidelines that tie recommended dosage to standardized "
     "assessment results, and documented an established, improving course of treatment.",
     "The reviewer found the requested intensity consistent with professional guidelines given "
     "the assessment results and ongoing clinical response."),
    ("FX-018", UP, "Autism Spectrum", "Behavioral Health", "Medical Necessity",
     ["peer-reviewed-evidence", "failed-alternatives"], [],
     "Insurer denied an increase in ABA therapy hours. The appeal cited general literature on "
     "ABA efficacy and asserted prior approaches had failed, but included no treatment records "
     "or assessment data supporting the claimed failure or the requested increase.",
     "The reviewer found no documentation substantiating the claimed failure of the current "
     "regimen and upheld the denial of additional hours."),
    ("FX-019", OT, "Autism Spectrum", "Behavioral Health", "Medical Necessity",
     ["failed-alternatives", "treating-physician-rationale"],
     ["prior-treatment-records", "physician-letter"],
     "Plan denied continuation of clinic-based ABA therapy, suggesting school-based services "
     "instead. Records showed school-only services had been tried the prior year with documented "
     "regression; the BCBA and pediatrician letters detailed why clinic-based intensity remained "
     "necessary.",
     "The reviewer credited the documented failure of the school-based alternative and the "
     "clinician rationale for continued clinic-based treatment."),
    ("FX-020", UP, "Autism Spectrum", "Behavioral Health", "Urgent Care",
     ["urgent-risk"], ["physician-letter"],
     "An expedited increase in ABA hours was requested citing an urgent behavioral crisis. The "
     "physician letter attested to urgency but the plan disputed that the standard review "
     "timeline posed imminent harm and denied the increase.",
     "The reviewer found the record did not establish imminent risk warranting the expedited "
     "increase and upheld the plan's determination."),
]

FIXTURE_PROFILES = [
    {"source_id": sid, "search_text": text, "diagnosis_category": diag,
     "treatment_category": treat, "denial_type": dtype, "outcome": outcome,
     "strategy_ids": strats, "evidence_present": ev, "is_fixture": True}
    for sid, outcome, diag, treat, dtype, strats, ev, text, _ in ROWS
]

FIXTURE_RAW = [
    {RAW_REF_FIELD: sid, RAW_DETERMINATION_FIELD: DET[outcome],
     RAW_FINDINGS_FIELD: findings, "is_fixture": True}
    for sid, outcome, _, _, _, _, _, _, findings in ROWS
]


def run():
    for coll in (DENIAL_PROFILES, IMR_DECISIONS):
        db[coll].delete_many({"is_fixture": True})
    for s in STRATEGY_CATALOG:
        db[STRATEGIES].replace_one({"_id": s["_id"]}, s, upsert=True)
    for e in EVIDENCE_CATALOG:
        db[EVIDENCE_TYPES].replace_one({"_id": e["_id"]}, e, upsert=True)
    db[DENIAL_PROFILES].insert_many(FIXTURE_PROFILES)
    db[IMR_DECISIONS].insert_many(FIXTURE_RAW)
    db[CASES].delete_many({})     # fresh demo state on reseed
    db[ATTEMPTS].delete_many({})
    print(f"profiles={db[DENIAL_PROFILES].count_documents({})} "
          f"raw={db[IMR_DECISIONS].count_documents({})} "
          f"strategies={db[STRATEGIES].count_documents({})} "
          f"evidence={db[EVIDENCE_TYPES].count_documents({})}")


if __name__ == "__main__":
    run()
