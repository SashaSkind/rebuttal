"""Closed taxonomy for denial_profiles.strategy_keys / evidence_keys.

Eyeball before pass 2. If a slug is generic, regenerate - do not classify 2k rows against mush.
"""

STRATEGIES = [
    {
        "key": "failed_preferred_alternative",
        "name": "Failed preferred alternative",
        "description": "Treating clinician documented that the plan-preferred drug, device, or conservative option was tried and failed or was not tolerated.",
        "example_phrasing": "Patient failed Enbrel and Cosentyx with documented inadequate response before requesting Taltz.",
    },
    {
        "key": "named_guideline_criteria",
        "name": "Named guideline / level-of-care criteria",
        "description": "Request meets a named standard (ASAM, CALOCUS-CASII, NCCN, AASM, etc.) for this service or intensity.",
        "example_phrasing": "Per ASAM criteria the patient meets Level 3.1 and is not stable for a lower level of care.",
    },
    {
        "key": "fda_labeled_indication",
        "name": "FDA-labeled indication",
        "description": "Requested drug or device is FDA-approved for this diagnosis and the patient meets the labeled population (e.g. class 3 obesity).",
        "example_phrasing": "Wegovy is FDA-approved for chronic weight management and BMI exceeds 40.",
    },
    {
        "key": "continuation_of_effective_therapy",
        "name": "Continuation of effective therapy",
        "description": "Patient is already on the requested therapy with documented clinical improvement or stability; stopping would lose that gain.",
        "example_phrasing": "Growth velocity and height improved on Omnitrope; continued therapy is appropriate.",
    },
    {
        "key": "literature_more_beneficial",
        "name": "Literature: more beneficial than standard",
        "description": "For experimental/investigational denials: published evidence that the requested service is likely more beneficial than available standard therapy.",
        "example_phrasing": "Literature supports implantable PNS when occipital injections and medications have diminishing benefit.",
    },
    {
        "key": "conservative_care_exhausted",
        "name": "Conservative care exhausted",
        "description": "Medications, PT, injections, or other non-operative care were completed without adequate relief before a procedure.",
        "example_phrasing": "Persistent axial back pain despite medication management and physical therapy before Intracept.",
    },
    {
        "key": "failed_lower_level_of_care",
        "name": "Failed or insufficient lower level of care",
        "description": "Outpatient, IOP, or a less intensive setting was tried or is clinically inadequate given current risk.",
        "example_phrasing": "Not yet clinically stable enough to step down from residential ASAM 3.1.",
    },
    {
        "key": "diagnostic_superiority",
        "name": "Diagnostic superiority vs plan alternative",
        "description": "Requested test/monitoring detects clinically relevant findings the plan's cheaper alternative would miss.",
        "example_phrasing": "Continuous mobile telemetry detects asymptomatic arrhythmias an event monitor would miss.",
    },
    {
        "key": "functional_impairment_despite_workup",
        "name": "Functional impairment despite 'normal' workup",
        "description": "Symptoms still impair daily function even if recent imaging/labs do not show active disease.",
        "example_phrasing": "Crohn's symptoms impair function despite recent evaluation without active inflammation.",
    },
    {
        "key": "structured_assessment_supports_intensity",
        "name": "Structured assessment supports intensity",
        "description": "A scored/structured tool (CALOCUS, ASAM dimensions, AHI, fibrosis stage) independently supports the requested intensity or drug.",
        "example_phrasing": "CALOCUS-CASII assessment meets criteria for weekly individual therapy.",
    },
]

EVIDENCE_TYPES = [
    {
        "key": "prior_failure_list",
        "name": "Prior therapy failure list",
        "description": "Named prior drugs/procedures with dates or duration and inadequate response or intolerance.",
        "example_phrasing": "Failed Enbrel and Cosentyx; inadequate response documented in rheumatology notes.",
    },
    {
        "key": "named_guideline_excerpt",
        "name": "Named guideline excerpt",
        "description": "Citation or quoted criteria from ASAM, NCCN, AASM, CALOCUS, AASLD, etc.",
        "example_phrasing": "ASAM Level 3.1 criteria met across multiple dimensions.",
    },
    {
        "key": "bmi_labs_growth",
        "name": "BMI, labs, or growth data",
        "description": "BMI, A1c, stimulation tests, percentiles, growth velocity, or other numeric criteria.",
        "example_phrasing": "Height below 3rd percentile; failed growth stimulation test.",
    },
    {
        "key": "treating_clinician_attestation",
        "name": "Treating clinician attestation",
        "description": "Office notes stating medical necessity, ongoing symptoms, or why the alternative is inappropriate.",
        "example_phrasing": "Endocrinology note: continued Omnitrope required to support growth.",
    },
    {
        "key": "response_on_current_therapy",
        "name": "Documented response on current therapy",
        "description": "Improvement in symptoms, function, height, or disease scores while on the requested service.",
        "example_phrasing": "Sustained improvement in psoriatic arthritis symptoms and function on Taltz.",
    },
    {
        "key": "peer_reviewed_literature",
        "name": "Peer-reviewed literature",
        "description": "Specific studies or reviews the reviewer relied on, especially for EI requests.",
        "example_phrasing": "Medical literature supports basivertebral nerve ablation for chronic axial low back pain.",
    },
    {
        "key": "level_of_care_records",
        "name": "Level-of-care / hospitalization records",
        "description": "RTC, PHP, ED, or inpatient notes showing risk and why step-down is unsafe.",
        "example_phrasing": "Residential records showing needs across ASAM dimensions; not stable for outpatient.",
    },
    {
        "key": "diagnostic_testing",
        "name": "Diagnostic testing",
        "description": "Imaging, cath, sleep study, autonomic testing, endoscopy, or similar objective tests.",
        "example_phrasing": "Impaired cardiac responses on autonomic testing.",
    },
    {
        "key": "lifestyle_or_supervised_program",
        "name": "Supervised conservative / lifestyle program",
        "description": "Documented medically supervised diet, PT course, or behavioral program with inadequate result.",
        "example_phrasing": "Completed medically supervised weight-loss program and behavioral therapy without adequate loss.",
    },
    {
        "key": "fda_label",
        "name": "FDA label / approved indication",
        "description": "Label language matching diagnosis and population.",
        "example_phrasing": "Zepbound FDA-approved for chronic weight management with obesity plus comorbidity.",
    },
]

STRATEGY_KEYS = [s["key"] for s in STRATEGIES]
EVIDENCE_KEYS = [e["key"] for e in EVIDENCE_TYPES]

# Pass 2: concentrate density here (CSV values, not our fixture labels)
FOCUS_DIAGNOSIS = [
    "Orth/Musculoskeletal",
    "Mental Disorder",
    "Cancer",
    "Endocrine/Metabolic",
]
