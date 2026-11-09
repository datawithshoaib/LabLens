# Safety and intended use

LabLens is intended to provide general education about laboratory terminology and the reference interval printed on a report. It is not a diagnostic or treatment tool.

## Rules implemented

- Numeric values are compared in ordinary code, never by a language model.
- Interval bounds are inclusive; invalid intervals and non-finite numbers are rejected.
- The API uses neutral labels (`low`, `within_range`, `high`) and includes a limitation statement.
- Reports can be uploaded, but there is no OCR or automatic extraction. Users enter and review result fields manually.
- A user must confirm a result before the API computes a numeric range status.
- The displayed status is a neutral comparison (`low`, `within_range`, or `high`) against the entered interval. It is not a diagnosis or urgency rating.

## Required before explanations or public use

- Preserve lab-provided flags and urgent instructions with page provenance; never downgrade them.
- Send ambiguous values, units, and ranges to user review. Never silently infer missing data.
- Cite reviewed educational sources for explanatory claims and validate citations against a curated registry.
- Avoid diagnoses, treatment recommendations, medication changes, false reassurance, and urgency ratings inferred solely from a general interval.
- Have qualified clinical reviewers approve user-facing safety copy, reviewed source material, and safety scenarios before public release.
- Complete a clinical safety case for the actual intended use and conduct evaluation with representative, appropriately governed data.
- Define an escalation path for critical values and report instructions. The current product does not triage or detect emergencies.
- Seek urgent local care for severe or rapidly worsening symptoms; the product must not substitute for emergency services.

An out-of-range comparison alone does not identify a cause. An in-range result does not establish health or rule out illness. Clinical interpretation depends on context and belongs with a qualified clinician.
