# LabLens --- Production-Grade AI Lab Report Explainer

**Technical Design Document**\
**Stack:** Python · FastAPI · LangChain · LangGraph · Next.js ·
shadcn/ui · PostgreSQL\
**Purpose:** Build a secure application that helps people understand
medical laboratory reports in plain language, highlights values relative
to the reference ranges printed on the report, provides carefully
sourced general explanations, and prepares questions for a qualified
healthcare professional.

> **Status:** This document describes the intended product and target architecture. The current implemented scope and outstanding launch gates are tracked in `README.md` and `docs/production-readiness.md`. In particular, OCR, automatic extraction, source-grounded explanations, and clinical evaluation are not implemented.

> **Critical safety boundary:** LabLens is an educational assistant, not
> a diagnostic or treatment tool. It must not diagnose a condition,
> recommend medication changes, or replace professional medical advice.
> A lab value alone is often insufficient to interpret a person's
> health. Results must be interpreted in context by a qualified
> clinician.

------------------------------------------------------------------------

## 1. Product Vision

LabLens lets a user upload a blood-test report as a PDF or image. It
extracts the reported tests, results, units, reference ranges, and
relevant report metadata. It then explains the extracted information in
plain language, identifies values that fall below or above the report's
stated reference range using deterministic code, links explanations to
trusted health sources, and suggests questions the user may ask their
clinician.

### Core features

1.  **Report ingestion:** Accept PDF and image uploads, including
    scanned reports.
2.  **Structured extraction:** Extract test names, measured values,
    units, reference ranges, flags, specimen date, and report metadata.
3.  **Deterministic range comparison:** Compare numeric results with the
    correct reference interval in code, not through LLM judgment.
4.  **Plain-language explanations:** Explain what a test measures and
    what high or low results can commonly be associated with, without
    claiming a diagnosis.
5.  **Trusted-source RAG:** Retrieve approved educational content from
    sources such as MedlinePlus and government health agencies.
6.  **Clinician discussion prompts:** Suggest neutral questions the user
    can take to their healthcare professional.
7.  **Review and correction:** Let users correct extraction errors
    before explanations are generated.
8.  **Safety controls:** Identify potentially urgent report instructions
    or clearly critical flags, while directing users to appropriate
    medical care instead of trying to triage them with an LLM.
9.  **Privacy and deletion:** Protect sensitive health information and
    provide clear retention and deletion controls.
10. **Evaluation:** Test extraction accuracy, reference-range logic,
    citation correctness, safety behavior, privacy controls, and
    reliability.

### Product principles

-   **Extract first, explain second.**
-   **Code determines range status; the LLM does not.**
-   **The report's own reference interval takes precedence for the
    initial comparison.**
-   **Every explanatory health claim should be traceable to a trusted
    source.**
-   **Uncertain or ambiguous data must be surfaced for user review, not
    silently guessed.**
-   **No diagnosis, individualized treatment plan, or medication change
    recommendation.**
-   **A normal range flag does not prove that a person is healthy; an
    out-of-range flag does not by itself establish disease.**

------------------------------------------------------------------------

## 2. Recommended Technology Stack

  --------------------------------------------------------------------------
  Layer                   Technology                 Purpose
  ----------------------- -------------------------- -----------------------
  Frontend                Next.js App Router,        Web application
                          TypeScript                 

  UI                      Tailwind CSS, shadcn/ui    Accessible interface

  PDF display             PDF.js / `react-pdf`       Report preview and page
                                                     navigation

  API                     FastAPI, Pydantic          Typed API and request
                                                     validation

  Workflow orchestration  LangGraph                  Bounded, auditable AI
                                                     workflow

  LLM integration         LangChain                  Prompts, model
                                                     interface, structured
                                                     output

  LLM provider            Configurable provider with Plain-language
                          suitable privacy terms     explanations

  OCR and PDF extraction  PyMuPDF plus OCR fallback  Text and page
                                                     extraction

  Table extraction        Docling or another         Table structure and
                          layout-aware parser        reading order

  Image processing        Pillow, optional OCR       Normalize image uploads
                          engine                     

  Database                PostgreSQL                 Users, reports,
                                                     extracted results,
                                                     audit records

  ORM/migrations          SQLAlchemy 2.x, Alembic    Data access and schema
                                                     changes

  Semantic retrieval      PostgreSQL + pgvector      Trusted-source
                                                     embeddings and
                                                     retrieval

  Background jobs         Celery or ARQ, choose one  OCR and report
                                                     processing

  Queue/cache             Redis                      Job queue and transient
                                                     state

  Object storage          Private                    Original reports and
                          S3-compatible/cloud object derived files
                          storage                    

  Validation              Pydantic and deterministic Validate extraction and
                          domain logic               range comparisons

  Testing                 pytest, pytest-asyncio     Unit, integration, and
                                                     API tests

  LLM evaluation          DeepEval plus              Evaluate explanation
                          domain-specific checks     quality and
                                                     groundedness

  Tracing                 LangSmith or               Debug workflow
                          OpenTelemetry-compatible   execution
                          tooling                    

  Logging                 Structured logging with    Operational diagnostics
                          redaction                  

  Packaging               uv                         Python dependencies and
                                                     lockfile

  Deployment              Docker, Docker Compose     Reproducible
                                                     environments

  CI/CD                   GitHub Actions             Tests, linting,
                                                     security and release
                                                     gates
  --------------------------------------------------------------------------

### Key decisions

-   Start as a **modular monolith** with separate API and worker
    processes.
-   Use PostgreSQL for application data and pgvector for trusted-source
    retrieval.
-   Keep range comparison in a deterministic Python domain service.
-   Use an LLM only after extracted results have been validated and
    assigned deterministic status.
-   Use a background worker for OCR, parsing, and other expensive
    operations.
-   Store uploaded reports in private object storage, not public URLs.
-   Do not send identifiable health data to an external model provider
    unless the provider, contract, configuration, and applicable legal
    requirements have been reviewed.
-   Do not claim regulatory compliance merely because encryption or
    authentication has been implemented. Applicable requirements depend
    on deployment, jurisdiction, intended use, and business model.

------------------------------------------------------------------------

## 3. System Architecture

``` mermaid
flowchart TD
    USER[User] --> WEB[Next.js + shadcn/ui]
    WEB --> API[FastAPI]
    API --> AUTH[Authentication, authorization, quotas]
    AUTH --> JOB[Create report and processing job]
    JOB --> QUEUE[Redis-backed task queue]
    QUEUE --> WORKER[Document processing worker]
    WORKER --> STORE[Private object storage]
    WORKER --> PARSE[PDF parsing and OCR]
    PARSE --> EXTRACT[Table and field extraction]
    EXTRACT --> REVIEW[Persist extracted results for review]
    REVIEW --> DB[(PostgreSQL)]
    DB --> RANGE[Deterministic reference-range service]
    RANGE --> STATUS[Validated result status]
    STATUS --> GRAPH[LangGraph explanation workflow]
    GRAPH --> RAG[Trusted-source retrieval]
    RAG --> VECTOR[(PostgreSQL + pgvector)]
    GRAPH --> LLM[Configured LLM provider]
    GRAPH --> GUARD[Output and safety validation]
    GUARD --> API
    API --> WEB
    GRAPH --> TRACE[Redacted traces and metrics]
    WORKER --> TRACE
```

### Processing flow

1.  Authenticate the user and verify upload permissions.
2.  Validate file type, size, and processing limits.
3.  Store the original report in private object storage.
4.  Create a durable processing job.
5.  Extract PDF text and tables; use OCR for scanned pages as needed.
6.  Convert extracted rows into typed candidate results.
7.  Validate test names, values, units, reference ranges, and page
    provenance.
8.  Ask the user to review ambiguous or low-confidence fields.
9.  Run deterministic comparison logic only on validated numeric values
    and valid intervals.
10. Retrieve relevant educational material from an approved
    health-source corpus.
11. Generate a plain-language explanation using only the validated
    result and retrieved context.
12. Validate claims, citations, and safety rules.
13. Display the report with uncertainty, provenance, and clinician
    discussion questions.
14. Retain data according to the user's consent and the application's
    retention policy.

Do not generate interpretations from unreviewed OCR output when a value,
unit, or range is ambiguous.

------------------------------------------------------------------------

## 4. Medical Safety and Scope

LabLens should be designed around a narrow, educational intended use.

### Allowed functionality

-   Explain what a laboratory test generally measures.
-   Compare a result with the reference interval printed on the report.
-   Explain common, non-diagnostic reasons a result may be high or low,
    with sources and caveats.
-   Explain why age, pregnancy status, symptoms, medicines, medical
    history, laboratory method, and other results can affect
    interpretation.
-   Suggest questions to discuss with a clinician.
-   Encourage professional follow-up when a result is flagged or the
    report instructs the patient to follow up.
-   Explain that the report's own reference interval may differ from
    intervals used by other laboratories.

### Disallowed functionality

-   Diagnosing a disease or asserting that a user has a condition.
-   Claiming a result proves that the user is healthy or ill.
-   Recommending starting, stopping, or changing medication or
    supplements.
-   Giving individualized treatment plans or medication dosages.
-   Overriding explicit urgent instructions from the laboratory or
    clinician.
-   Assigning an urgency level solely from a general reference range or
    an LLM-generated interpretation.
-   Fabricating medical references or implying that a source reviewed
    the user's personal case.

### Safety language

Use clear, calm wording such as:

> LabLens is an educational tool. It can explain the terms and reference
> ranges shown on your report, but it cannot diagnose a condition. A
> result outside the reference range does not automatically mean that
> you have a disease, and a result within range does not rule one out.
> Your clinician can interpret these findings alongside your symptoms,
> medical history, medicines, and other tests.

This message should be visible during onboarding and near report
explanations, not hidden only in the terms of service.

### Urgent situations

-   Preserve and prominently display any explicit critical-value alert
    or urgent instruction found in the report, with its source and page.
-   Do not attempt to reinterpret or downgrade an explicit laboratory or
    clinician instruction.
-   If a report contains a clearly documented critical flag, direct the
    user to follow the report's instructions and contact the ordering
    clinician or appropriate medical service promptly.
-   If a user reports severe or rapidly worsening symptoms, advise them
    to seek urgent local medical care or emergency services rather than
    relying on the application.
-   Do not invent a universal critical threshold. Critical values can
    depend on the test, laboratory, patient context, and local clinical
    policy.

Have qualified clinical reviewers approve safety copy, escalation
behavior, source content, and any test-specific explanations before
public release.

------------------------------------------------------------------------

## 5. PDF, OCR, and Table Extraction

Lab reports are difficult because they may use multi-column layouts,
compact tables, abbreviations, bold flags, different units, and
reference intervals that vary by age or sex. OCR may confuse decimal
points, minus signs, or adjacent columns.

### Extraction pipeline

``` mermaid
flowchart TD
    A[PDF or image upload] --> B[Validate file and store privately]
    B --> C{Text extractable?}
    C -->|Yes| D[PDF text and layout extraction]
    C -->|No| E[OCR pipeline]
    D --> F[Detect tables and result rows]
    E --> F
    F --> G[Normalize candidate fields]
    G --> H[Validate units, values and intervals]
    H --> I{Sufficient confidence?}
    I -->|Yes| J[Ready for user review]
    I -->|No| K[Request correction or manual review]
    J --> L[Deterministic range comparison]
```

### Recommended parsing approach

-   **PyMuPDF:** extract text, page numbers, and PDF metadata.
-   **Docling:** consider for layout-aware parsing and tables.
-   **OCR engine:** select and evaluate an OCR engine for scanned
    documents and image uploads. Keep OCR as a distinct pipeline stage.
-   **Pillow:** normalize image orientation and size where necessary.
-   **Pydantic:** validate normalized candidate rows.

Do not rely on plain text extraction alone when column alignment
matters. Preserve the original page image or PDF view so users can
verify extracted values.

### Candidate extraction schema

``` python
from decimal import Decimal
from pydantic import BaseModel, Field


class ExtractedLabResult(BaseModel):
    test_name_raw: str
    test_name_normalized: str | None = None
    value: Decimal | None = None
    value_text: str | None = None
    unit_raw: str | None = None
    reference_low: Decimal | None = None
    reference_high: Decimal | None = None
    reference_text: str | None = None
    lab_flag_raw: str | None = None
    specimen_date: str | None = None
    page_number: int = Field(ge=1)
    extraction_confidence: float = Field(ge=0, le=1)
    needs_review: bool = False
```

The schema is illustrative. In production, represent qualitative values,
inequalities such as `<5`, multiple reference intervals, and missing
ranges explicitly rather than coercing them into a numeric value.

### Extraction rules

-   Preserve the raw extracted text as well as normalized fields.
-   Never silently guess a missing unit or reference interval.
-   Do not assume all reference ranges are a simple lower/upper pair.
-   Preserve flags printed by the laboratory, such as `H`, `L`, or
    `Critical`, but do not treat them as infallible without checking the
    row alignment.
-   Store page number and enough source coordinates or layout references
    to help users verify the extraction.
-   Mark ambiguous fields for review before generating explanations.
-   Record parser/OCR engine version and extraction configuration for
    debugging.

### Confidence handling

Confidence should be calibrated using a representative labelled dataset.
Do not use an arbitrary confidence threshold as a medical safety
guarantee. If a value or reference range is ambiguous, require user
review or route to a safe failure state.

------------------------------------------------------------------------

## 6. Deterministic Reference-Range Logic

**This is a core architectural requirement: comparison logic belongs in
ordinary Python code, not in the LLM prompt.**

The application should compare a validated numeric result against the
reference interval extracted from that same report. It should not
substitute a generic internet range.

### Basic status model

For a valid inclusive interval `[low, high]`:

-   Below range: `value < low`
-   Within range: `low <= value <= high`
-   Above range: `value > high`
-   Not assessable: missing or invalid value/range, qualitative result,
    unsupported interval, or unresolved extraction ambiguity

Use `Decimal` for decimal values when precision matters. Validate that
the lower bound is not greater than the upper bound.

### Example implementation

``` python
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, model_validator


class RangeStatus(StrEnum):
    LOW = "low"
    WITHIN_RANGE = "within_range"
    HIGH = "high"
    NOT_ASSESSABLE = "not_assessable"


class NumericReferenceRange(BaseModel):
    value: Decimal
    low: Decimal
    high: Decimal

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.low > self.high:
            raise ValueError("Reference lower bound exceeds upper bound")
        return self


def compare_to_reference_range(
    result: NumericReferenceRange | None,
) -> RangeStatus:
    if result is None:
        return RangeStatus.NOT_ASSESSABLE

    if result.value < result.low:
        return RangeStatus.LOW

    if result.value > result.high:
        return RangeStatus.HIGH

    return RangeStatus.WITHIN_RANGE
```

`StrEnum` is available in Python 3.11 and later. If using an earlier
Python version, use `class RangeStatus(str, Enum)`.

### Production requirements beyond the simple example

The simple implementation covers only a numeric result and one inclusive
interval. Real lab reports require explicit handling of:

-   Lower-only or upper-only bounds.
-   Qualitative results such as positive, negative, reactive, or
    detected.
-   Inequality results such as `<`, `>`, or `below detection limit`.
-   Multiple intervals selected by age, sex, pregnancy status, specimen
    type, or laboratory method.
-   Missing or conflicting units.
-   Unit conversions, only when scientifically valid and implemented
    through reviewed conversion rules.
-   Laboratory-specific flags and explicit critical alerts.
-   Reference interval text that could not be parsed confidently.

Do not force these cases into the basic numeric model. Return
`not_assessable` until the relevant rule is implemented and validated.

### Unit safety

Never compare values with incompatible units. A numeric result of `5`
cannot be compared with a reference range of `3–7` unless the units and
analyte context are known to match.

-   Preserve original units.
-   Normalize only using explicit, tested conversion rules.
-   Record both original and normalized values when conversion occurs.
-   Do not infer units from the test name alone.
-   Treat unknown or incompatible units as not assessable.

### Range status is not a diagnosis

The result status means only that the value falls below, inside, or
above the reference interval used for comparison. It does not determine
disease, severity, or urgency.

Keep these concepts separate in the database and UI:

-   `range_status`: deterministic comparison result.
-   `lab_report_flag`: flag extracted from the report.
-   `critical_alert_present`: explicit alert detected from the report,
    with provenance and review status.
-   `clinical_interpretation`: a sourced educational explanation, never
    a diagnosis.
-   `extraction_review_status`: whether the extracted fields were
    confirmed.

------------------------------------------------------------------------

## 7. Trusted-Source RAG

RAG should provide general educational context from an approved, curated
source collection. It should not turn a broad web search into
personalized diagnosis.

### Source policy

Prefer trusted public health and medical education sources, for example:

-   MedlinePlus, operated by the U.S. National Library of Medicine.
-   National Institutes of Health resources.
-   Relevant government health agencies.
-   Recognized health-system educational resources reviewed by qualified
    clinicians.
-   Laboratory-specific educational material when its provenance and
    scope are clear.

The source allowlist should be documented, reviewed, and versioned. A
source being popular or highly ranked in a search result is not enough
to make it medically trustworthy.

### Ingestion pipeline for trusted sources

1.  Define a source allowlist and permitted retrieval method for each
    provider.
2.  Collect only content permitted by the source's terms and access
    policy.
3.  Record title, publisher, canonical URL, publication/update date when
    available, retrieval date, and content version.
4.  Split content by heading and semantic section.
5.  Generate embeddings and store chunks with source metadata.
6.  Refresh content on a scheduled basis and mark outdated or removed
    pages.
7.  Exclude sources that fail provenance or quality checks.

Do not crawl sites indiscriminately. Respect API terms, robots
directives where applicable, licensing, copyright, and rate limits.

### Retrieval process

1.  Build a retrieval query from the normalized test name and the user's
    selected explanation request.
2.  Search only the approved corpus.
3.  Apply source and content filters.
4.  Retrieve relevant passages and optionally rerank them.
5.  Generate a plain-language explanation with citations to those
    passages.
6.  Verify that each citation refers to a retrieved, stored source
    record.
7.  Return a safe, limited response if evidence is weak or
    contradictory.

### Example source record

``` python
{
    "source_id": "source-uuid",
    "title": "Example educational article about a laboratory test",
    "publisher": "Approved health organization",
    "canonical_url": "https://example.org/health-topic",
    "published_at": None,
    "updated_at": None,
    "retrieved_at": "2026-01-01T00:00:00Z",
    "content_version": "sha256:...",
    "section_title": "Understanding the test",
    "chunk_text": "...",
    "review_status": "approved"
}
```

The example URL and dates are placeholders. Store real source metadata
when ingesting actual approved content.

### Citation requirements

Each health explanation should include source links and, where
practical, a short supporting excerpt. The system must not fabricate a
title, URL, publisher, date, or quotation. If the evidence is
insufficient, say so.

------------------------------------------------------------------------

## 8. LangGraph Workflow and AI Responsibilities

Use LangGraph to orchestrate bounded steps, but keep medical rules
outside the LLM.

### Workflow

``` mermaid
flowchart TD
    START([START]) --> INPUT[Validate user request and report access]
    INPUT --> EXTRACTED[Load reviewed structured lab results]
    EXTRACTED --> RULES[Run deterministic range comparison]
    RULES --> RETRIEVE[Retrieve approved health education sources]
    RETRIEVE --> EXPLAIN[Generate plain-language explanation]
    EXPLAIN --> VALIDATE[Validate citations, schema and safety]
    VALIDATE -->|Pass| PRESENT[Persist and return explanation]
    VALIDATE -->|Repairable output issue| RETRY[Bounded regeneration]
    RETRY --> VALIDATE
    VALIDATE -->|Still invalid or unsafe| SAFE[Return limited safe response]
    PRESENT --> END([END])
    SAFE --> END
```

### Suggested nodes

  -----------------------------------------------------------------------
  Node                    Responsibility          May use an LLM?
  ----------------------- ----------------------- -----------------------
  Input validator         Check request,          No
                          permissions, and        
                          selected report         

  Extraction loader       Load confirmed          No
                          structured values       

  Range comparator        Apply deterministic     No
                          comparison rules        

  Source retriever        Retrieve approved       Optional query
                          educational sources     rewriting, bounded

  Explanation generator   Explain the test and    Yes
                          common associations     

  Citation validator      Verify source IDs and   No
                          URLs against stored     
                          records                 

  Safety validator        Enforce output schema   Primarily
                          and prohibited claims   deterministic; optional
                                                  secondary classifier

  Response formatter      Build the response from No
                          validated fields        
  -----------------------------------------------------------------------

The LLM must not set `range_status`, invent a critical alert, choose a
medication, or make a diagnosis. If a classifier is used to detect
unsafe text, it should be a defense-in-depth measure, not the sole
safety barrier.

### Example state

``` python
from typing import TypedDict


class LabLensState(TypedDict, total=False):
    user_id: str
    report_id: str
    reviewed_results: list[dict]
    range_comparisons: list[dict]
    retrieved_sources: list[dict]
    explanations: list[dict]
    validation_errors: list[str]
    retry_count: int
```

Use only the minimum necessary data in graph state. Avoid putting direct
identifiers or full report content into traces unless strictly necessary
and approved under the privacy policy.

### Failure behavior

-   Unreviewed ambiguous result: request correction instead of
    interpreting.
-   Unknown unit or unsupported range: mark not assessable.
-   No relevant approved source: provide a limited explanation or state
    that the system could not find enough approved evidence.
-   Invalid citation: reject the output or retry once.
-   Diagnosis or treatment recommendation in generated text: block it
    and return a safe response.
-   External model outage: show a recoverable error; do not fabricate an
    explanation.
-   Explicit critical report instruction: preserve the alert and direct
    the user to follow the report's instructions and contact the
    relevant healthcare professional promptly.

------------------------------------------------------------------------

## 9. Explanation Output Contract

Use structured outputs so the UI can clearly distinguish measured facts,
deterministic flags, educational context, and next-step questions.

### Example response schema

``` python
from typing import Literal
from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    source_id: str
    title: str
    url: str
    supporting_excerpt: str | None = None


class LabExplanation(BaseModel):
    test_name: str
    reported_value: str
    reported_unit: str | None = None
    reference_range_text: str | None = None
    range_status: Literal[
        "low",
        "within_range",
        "high",
        "not_assessable",
    ]
    what_the_test_measures: str
    common_associations: list[str] = Field(default_factory=list)
    important_context: list[str] = Field(default_factory=list)
    questions_for_clinician: list[str] = Field(default_factory=list)
    citations: list[SourceCitation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
```

The API should populate `range_status` from the deterministic service.
Do not accept an LLM-provided value for that field as authoritative.

### Output design rules

-   Show the exact reported value and unit.
-   Show the exact reference range from the report when available.
-   Explain that ranges vary by laboratory and patient context.
-   Label educational associations as possibilities, not conclusions.
-   Avoid assigning a disease probability unless the product has a
    clinically validated and legally reviewed basis to do so; this MVP
    should not calculate one.
-   Include source citations for medical claims.
-   Display extraction uncertainty and allow correction.
-   Offer questions for a clinician rather than a diagnosis or treatment
    plan.

### Example user-facing wording

> **Your result is below the reference interval shown on this report.**
> This comparison describes the number relative to this laboratory's
> stated range; it does not identify the cause. Some results can be
> affected by medicines, recent illness, nutrition, or other factors.
> Your clinician can interpret it alongside your medical history and
> other findings.

This is generic sample wording, not an interpretation of a real test.

------------------------------------------------------------------------

## 10. FastAPI API Design

Keep routes thin and place business logic in services.

  ---------------------------------------------------------------------------------------------------
  Method                  Endpoint                                            Purpose
  ----------------------- --------------------------------------------------- -----------------------
  POST                    `/api/v1/reports`                                   Upload report and
                                                                              create processing job

  GET                     `/api/v1/reports`                                   List current user's
                                                                              reports

  GET                     `/api/v1/reports/{report_id}`                       Get report metadata and
                                                                              status

  DELETE                  `/api/v1/reports/{report_id}`                       Delete report and
                                                                              associated data
                                                                              according to retention
                                                                              policy

  GET                     `/api/v1/jobs/{job_id}`                             Poll processing status

  GET                     `/api/v1/reports/{report_id}/results`               Get extracted test rows
                                                                              and review state

  PATCH                   `/api/v1/reports/{report_id}/results/{result_id}`   Correct an extracted
                                                                              field

  POST                    `/api/v1/reports/{report_id}/confirm-results`       Confirm reviewed
                                                                              extraction

  POST                    `/api/v1/reports/{report_id}/explanations`          Generate explanations
                                                                              for confirmed results

  GET                     `/api/v1/reports/{report_id}/sources`               Retrieve citations used
                                                                              for explanations

  POST                    `/api/v1/feedback`                                  Submit usefulness or
                                                                              safety feedback

  GET                     `/health/live`                                      Liveness probe

  GET                     `/health/ready`                                     Readiness probe
  ---------------------------------------------------------------------------------------------------

Require authentication and ownership checks on all report-specific
endpoints. Add pagination, rate limiting, standardized errors, and
request IDs.

### Example upload response

``` json
{
  "report_id": "report-uuid",
  "job_id": "job-uuid",
  "status": "queued"
}
```

### Example processing status

``` json
{
  "job_id": "job-uuid",
  "status": "awaiting_review",
  "progress_stage": "field_validation",
  "needs_user_review": true
}
```

Do not include extracted health details in status endpoints unless
required. Keep status payloads minimal.

------------------------------------------------------------------------

## 11. Frontend --- Next.js and shadcn/ui

### Suggested routes

  Route                           Purpose
  ------------------------------- ---------------------------------------------
  `/`                             Product introduction and safety information
  `/dashboard`                    Report library and upload entry point
  `/reports/[reportId]`           Report preview and processing status
  `/reports/[reportId]/review`    Confirm or correct extracted results
  `/reports/[reportId]/results`   Range comparisons and explanations
  `/settings/privacy`             Retention, export, and deletion controls
  `/admin/evaluations`            Restricted evaluation dashboard

### Components

-   `ReportUploadDialog`
-   `PDFReportViewer`
-   `ProcessingStatus`
-   `ExtractedResultsTable`
-   `FieldCorrectionDialog`
-   `ReferenceRangeBadge`
-   `LabResultCard`
-   `PlainLanguageExplanation`
-   `SourceCitationList`
-   `ClinicianQuestionList`
-   `SafetyNotice`
-   `DeleteReportDialog`
-   `FeedbackControls`

### UI principles

-   Use neutral labels such as "Below range," "Within range," and "Above
    range," rather than disease labels.
-   Do not use color as the only way to convey status; include text and
    accessible icons.
-   Show the lab's own reference range and units next to the result.
-   Allow the user to open the original report page to verify extracted
    data.
-   Make uncertain values visibly require review.
-   Display sources adjacent to the explanations they support.
-   Keep the non-diagnosis notice visible without making the experience
    frightening.
-   Do not show a fabricated "health score" or combine results into an
    unsupported risk rating.
-   Render model-generated Markdown safely.
-   Do not send secrets or privileged evaluation data to the browser.

------------------------------------------------------------------------

## 12. Database Design

Use PostgreSQL with SQLAlchemy and Alembic.

  -------------------------------------------------------------------------
  Table                     Key fields              Purpose
  ------------------------- ----------------------- -----------------------
  `users`                   `id`, `email`,          Accounts
                            `created_at`            

  `reports`                 `id`, `owner_id`,       Uploaded reports
                            `storage_key`,          
                            `status`, `created_at`  

  `processing_jobs`         `id`, `report_id`,      Durable job state
                            `status`, `attempts`,   
                            `error_code`            

  `report_pages`            `id`, `report_id`,      Page provenance
                            `page_number`,          
                            `extraction_metadata`   

  `lab_results`             `id`, `report_id`,      Extracted result fields
                            `test_name_raw`,        
                            `value`, `unit`,        
                            `range_text`,           
                            `page_number`,          
                            `review_status`         

  `range_comparisons`       `id`, `lab_result_id`,  Deterministic
                            `status`,               comparison result
                            `rule_version`,         
                            `created_at`            

  `trusted_sources`         `id`, `publisher`,      Approved source
                            `title`,                registry
                            `canonical_url`,        
                            `content_version`,      
                            `review_status`         

  `source_chunks`           `id`, `source_id`,      RAG corpus
                            `text`, `section`,      
                            `embedding`             

  `explanations`            `id`, `lab_result_id`,  Generated educational
                            `schema_version`,       explanations
                            `content_json`          

  `explanation_citations`   `explanation_id`,       Citation provenance
                            `source_chunk_id`       

  `user_feedback`           `id`, `report_id`,      Quality feedback
                            `feedback_type`,        
                            `created_at`            

  `audit_events`            `id`, `user_id`,        Security-relevant
                            `action`,               actions
                            `resource_id`,          
                            `created_at`            
  -------------------------------------------------------------------------

### Data rules

-   Use UUIDs for internal identifiers.
-   Apply row ownership checks in application logic and, where
    appropriate, database-level policies.
-   Keep original extraction text separate from normalized fields.
-   Store units and reference intervals exactly as reported.
-   Store a version for range-comparison rules and extraction pipeline.
-   Track which explanation and source chunks were used for each result.
-   Avoid retaining full prompts or report text in operational logs.
-   Apply a documented deletion policy across database, object storage,
    vectors, caches, backups where feasible, and observability systems.
-   Keep evaluation datasets synthetic or properly de-identified. Do not
    use identifiable health reports for model evaluation without
    explicit authorization and appropriate legal and privacy review.

------------------------------------------------------------------------

## 13. Evaluation Framework

LabLens needs domain-specific evaluation, not only generic LLM quality
scores. Separate deterministic tests from LLM-judged tests and human
clinical review.

### 13.1 Evaluation layers

#### A. Extraction accuracy

-   Test name exactness and normalized mapping.
-   Numeric value accuracy, including decimals and signs.
-   Unit accuracy.
-   Reference interval extraction accuracy.
-   Correct page and row association.
-   OCR error rates across scanned and digitally generated PDFs.
-   Confidence calibration and review-trigger recall.

#### B. Deterministic logic

-   Boundary tests for lower and upper values.
-   Invalid intervals.
-   Missing values or ranges.
-   Qualitative results and inequality values.
-   Unit mismatch handling.
-   Correct `not_assessable` behavior.
-   No accidental comparison across incompatible analytes or units.

These should primarily be deterministic unit tests, not LLM evaluations.

#### C. RAG and explanation quality

-   Source relevance.
-   Citation validity.
-   Groundedness in retrieved trusted sources.
-   Completeness without unsupported detail.
-   Plain-language readability.
-   Accurate distinction between general associations and conclusions
    about the user.

#### D. Safety

-   No diagnosis claims.
-   No medication change advice.
-   No unsupported treatment recommendations.
-   No false reassurance from in-range values.
-   No overstatement from out-of-range values.
-   Correct handling of explicit critical report instructions.
-   Appropriate safe behavior when evidence is insufficient.
-   Prompt injection resistance.

#### E. Operational reliability

-   Processing success and failure rates.
-   p50/p95 processing duration.
-   API latency and error rates.
-   Queue delay.
-   Model token usage and cost.
-   Retry and cancellation behavior.

### 13.2 Golden dataset

Create a labelled dataset of de-identified or synthetic reports. Begin
with a manageable collection covering common table formats, different
units, scanned reports, reference interval variants, and deliberately
ambiguous cases. Have qualified reviewers validate medical explanation
references and safety scenarios before release.

Each test record can include:

``` json
{
  "case_id": "synthetic-case-001",
  "document_type": "digital_pdf",
  "expected_results": [
    {
      "test_name_raw": "Example Test",
      "value": "4.2",
      "unit": "unit-example",
      "reference_range_text": "3.0 - 5.0",
      "expected_range_status": "within_range"
    }
  ],
  "expected_review_required": false,
  "safety_case": "routine_educational_explanation"
}
```

All values here are illustrative, not medical guidance. Do not reuse
this fictional test as a real laboratory reference range.

### 13.3 Example deterministic tests

``` python
from decimal import Decimal
import pytest


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2.9", "low"),
        ("3.0", "within_range"),
        ("4.0", "within_range"),
        ("5.0", "within_range"),
        ("5.1", "high"),
    ],
)
def test_reference_range_boundaries(value, expected):
    result = NumericReferenceRange(
        value=Decimal(value),
        low=Decimal("3.0"),
        high=Decimal("5.0"),
    )

    assert compare_to_reference_range(result).value == expected
```

This tests software boundary behavior only. The numbers are fictional
and must not be interpreted as a real clinical range.

### 13.4 LLM evaluation

Use DeepEval or a similar evaluation framework for answer groundedness,
relevancy, and safety-oriented test cases. Use LangSmith or compatible
tracing to inspect workflow executions. Do not rely on an LLM judge
alone for medical safety.

A release gate should require: - 100% pass rate on deterministic
range-comparison tests. - 100% citation ID and source URL validity in
the test set. - No critical violations in the curated safety test
suite. - A measured and reviewed extraction accuracy target for each
supported document class. - Human review of clinically meaningful
failures. - No unexplained regression against the previous approved
evaluation baseline.

Targets should be defined and justified using a representative dataset.
Passing an automated benchmark does not establish clinical validity or
regulatory compliance.

### 13.5 CI policy

Every pull request should run: 1. Linting and type checks. 2. Unit tests
for extraction normalization and range logic. 3. API and database
integration tests. 4. Access control and deletion tests. 5. Citation and
schema tests. 6. A fast safety regression suite. 7. LLM evaluations when
prompts, models, retrieval, or safety behavior changes.

Run the full evaluation suite on a schedule and before significant
releases. Version the dataset, prompt, model configuration, extraction
pipeline, and comparison rules.

------------------------------------------------------------------------

## 14. Repository Structure

``` text
lablens/
├── apps/
│   └── web/
│       ├── app/
│       │   ├── dashboard/
│       │   ├── reports/[reportId]/
│       │   ├── reports/[reportId]/review/
│       │   ├── reports/[reportId]/results/
│       │   ├── settings/privacy/
│       │   └── admin/evaluations/
│       ├── components/
│       ├── hooks/
│       ├── lib/
│       └── package.json
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── alembic.ini
│   ├── alembic/
│   ├── src/lablens/
│   │   ├── main.py
│   │   ├── api/v1/
│   │   │   ├── reports.py
│   │   │   ├── results.py
│   │   │   ├── explanations.py
│   │   │   ├── sources.py
│   │   │   └── feedback.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   ├── db/
│   │   │   ├── session.py
│   │   │   ├── models/
│   │   │   └── repositories/
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── report_service.py
│   │   │   ├── extraction_service.py
│   │   │   ├── range_service.py
│   │   │   ├── retrieval_service.py
│   │   │   └── explanation_service.py
│   │   ├── ingestion/
│   │   │   ├── pdf_parser.py
│   │   │   ├── ocr.py
│   │   │   ├── table_extraction.py
│   │   │   └── normalization.py
│   │   ├── agents/
│   │   │   ├── state.py
│   │   │   ├── graph.py
│   │   │   ├── nodes/
│   │   │   └── prompts/
│   │   ├── safety/
│   │   │   ├── policies.py
│   │   │   ├── validators.py
│   │   │   └── escalation.py
│   │   ├── workers/
│   │   │   └── tasks.py
│   │   └── evals/
│   │       ├── datasets/
│   │       ├── extraction_tests.py
│   │       ├── range_tests.py
│   │       ├── safety_tests.py
│   │       └── runner.py
│   └── tests/
│       ├── unit/
│       ├── integration/
│       ├── api/
│       ├── security/
│       └── evals/
├── infra/
│   ├── docker/
│   └── compose.yaml
├── docs/
│   ├── architecture.md
│   ├── safety.md
│   ├── privacy.md
│   ├── evaluation.md
│   └── data-retention.md
├── .github/workflows/
├── .env.example
├── .gitignore
└── README.md
```

### Code quality rules

-   Use type hints throughout Python and strict TypeScript.
-   Validate all external input with Pydantic or equivalent schema
    validation.
-   Keep deterministic domain logic independent of FastAPI and LLM
    libraries.
-   Keep database transactions short; do not hold them open during OCR
    or LLM calls.
-   Use idempotent background jobs.
-   Add timeouts and bounded retries to external calls.
-   Redact sensitive information from logs and traces.
-   Use database migrations rather than automatic production table
    creation.
-   Keep model, parser, OCR, prompt, and range-rule versions in
    configuration or metadata.
-   Add tests for failure modes and access control, not only successful
    requests.

------------------------------------------------------------------------

## 15. Development Setup

Use `uv` for Python dependency management and commit `uv.lock`. Resolve
exact versions in the working environment rather than relying on
floating versions.

### Backend setup

``` bash
mkdir lablens
cd lablens

uv init backend
cd backend

uv python pin 3.12
uv add fastapi "uvicorn[standard]" pydantic \
  pydantic-settings python-multipart

uv add langchain langgraph langchain-openai \
  langchain-text-splitters langsmith

uv add sqlalchemy asyncpg alembic \
  pgvector "psycopg[binary]" redis celery

uv add pymupdf pillow httpx tenacity structlog

uv add --dev pytest pytest-asyncio ruff mypy deepeval

uv lock
```

Add a layout-aware parser and OCR engine after selecting and testing the
specific libraries for the target deployment. OCR dependencies can be
large and may require separate system packages or worker images.

Python 3.12 is a conservative starting point. Test Python 3.13
compatibility before upgrading. The locked dependency set and container
build should be tested together.

### Frontend setup

``` bash
cd ..

npx create-next-app@latest apps/web \
  --typescript --tailwind --eslint --app

npx shadcn@latest init -t next

cd apps/web

npx shadcn@latest add button card dialog \
  dropdown-menu input skeleton tabs tooltip sonner
```

Add the PDF viewer and query client when needed.

### Environment variables

``` dotenv
APP_ENV=development
API_V1_PREFIX=/api/v1

DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/lablens
REDIS_URL=redis://localhost:6379/0

LLM_PROVIDER=openai
LLM_MODEL=your-configured-model
EMBEDDING_MODEL=your-configured-embedding-model
OPENAI_API_KEY=

LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=lablens-development

OBJECT_STORAGE_ENDPOINT=
OBJECT_STORAGE_BUCKET=lablens-reports
OBJECT_STORAGE_ACCESS_KEY=
OBJECT_STORAGE_SECRET_KEY=

AUTH_SECRET=
FRONTEND_ORIGIN=http://localhost:3000
```

Model identifiers are placeholders. Never commit real secrets. Enable
tracing only after reviewing what data is sent to the tracing service;
configure redaction and retention before processing real health data.

------------------------------------------------------------------------

## 16. Privacy, Security, and Compliance

Lab reports contain sensitive personal health information. Privacy must
shape the architecture from the start.

### Minimum security requirements

-   Authentication and per-resource authorization.
-   TLS in transit and encryption at rest.
-   Private object storage and short-lived signed access URLs where
    needed.
-   Upload size, file type, page count, and processing time limits.
-   Parser and OCR worker isolation.
-   Rate limits and abuse controls.
-   Secret management outside source control.
-   Audit records for report access, export, and deletion.
-   Defined data retention and deletion procedures.
-   Backups and tested restoration.
-   Dependency and container vulnerability scanning.
-   Secure error responses that do not leak report content.
-   Protection against prompt injection in reports and retrieved
    documents.
-   Restricted administrative and evaluation endpoints.

### Privacy-by-design

-   Collect only data needed for the feature.
-   Avoid collecting symptoms, age, sex, pregnancy status, or other
    personal context unless necessary for a clearly defined feature and
    supported by an appropriate privacy design.
-   Do not infer missing demographic attributes.
-   Explain whether reports are sent to third-party model or OCR
    services.
-   Obtain appropriate consent and verify contractual, jurisdictional,
    and regulatory requirements before using external processors.
-   Do not use uploaded reports to train or evaluate models by default.
-   Prefer synthetic or properly de-identified test data.
-   Provide a clear user deletion workflow and document the limits of
    deletion from backups and third-party systems.
-   Configure observability to avoid retaining report contents,
    extracted values, and prompts unless there is a documented,
    authorized need.

### Compliance caveat

Do not claim HIPAA, GDPR, or other compliance based on technology
choices alone. Applicability and required controls depend on
jurisdiction, business relationships, intended use, and the actual data
flow. Obtain qualified legal, privacy, and clinical review before
handling real users' health reports at scale.

------------------------------------------------------------------------

## 17. Deployment Architecture

``` mermaid
flowchart TD
    WEB[Next.js hosting] --> API[FastAPI service]
    API --> DB[(Managed PostgreSQL + pgvector)]
    API --> REDIS[(Redis / task queue)]
    REDIS --> WORKER[Isolated processing worker]
    WORKER --> STORE[(Private object storage)]
    WORKER --> OCR[PDF parser / OCR]
    API --> LLM[Approved LLM provider]
    API --> RAG[Trusted-source retrieval]
    RAG --> DB
    API --> OBS[Redacted logs and metrics]
    WORKER --> OBS
```

### Production checklist

-   Separate API and worker processes.
-   Private object storage and access controls.
-   Managed PostgreSQL with backups and pgvector support.
-   Redis for the selected task queue.
-   HTTPS and correct CORS configuration.
-   Health and readiness endpoints.
-   Structured logs with sensitive-field redaction.
-   Database migrations in the release pipeline.
-   Staging environment with synthetic reports.
-   CI checks for tests, safety regressions, and dependencies.
-   Worker CPU, memory, page-count, and time limits.
-   Alerting for processing failures, queue delays, and external
    provider outages.
-   Verified data retention and deletion behavior.

Use Docker Compose locally for API, worker, PostgreSQL, Redis, and
supporting services. Deploy managed infrastructure where possible rather
than starting with Kubernetes.

------------------------------------------------------------------------

## 18. Implementation Roadmap

### Phase 1 --- Foundation

Create the repository, configuration, database models, migrations,
FastAPI health endpoint, Docker Compose, and frontend shell.

**Deliverable:** a reproducible full-stack development environment.

### Phase 2 --- Extraction and review

Implement upload validation, private storage, PDF parsing, OCR fallback,
table extraction, normalized candidate fields, and the review UI.

**Deliverable:** users can inspect and correct extracted values before
interpretation.

### Phase 3 --- Deterministic range logic

Implement numeric comparison, boundary tests, unit validation,
unsupported-range behavior, and versioned rules.

**Deliverable:** reproducible status labels independent of the LLM.

### Phase 4 --- Trusted-source RAG

Curate approved health education sources, ingest source metadata, build
retrieval, generate cited plain-language explanations, and validate
source links.

**Deliverable:** explanations with traceable references and clear
uncertainty.

### Phase 5 --- LangGraph and safety

Orchestrate the workflow, add output schema validation, safe failure
behavior, prompt injection tests, and clinician question generation.

**Deliverable:** a bounded, testable explanation workflow.

### Phase 6 --- Evaluation and production hardening

Build the labelled dataset, add extraction and safety metrics, integrate
observability, implement deletion and retention, secure the deployment,
and establish release gates.

**Deliverable:** a deployed educational assistant with measured
limitations and repeatable releases.

------------------------------------------------------------------------

## 19. Definition of Done

### Product

-   [ ] Upload digitally generated PDFs and supported image/scanned
    reports.
-   [ ] Display extraction progress and processing errors.
-   [ ] Show extracted values, units, reference intervals, and source
    pages.
-   [ ] Require correction or review for ambiguous extraction.
-   [ ] Calculate numeric range status with deterministic code.
-   [ ] Explain results in plain language with trusted-source citations.
-   [ ] Suggest questions for a healthcare professional.
-   [ ] Display clear non-diagnosis boundaries and safe follow-up
    guidance.
-   [ ] Allow report deletion and explain retention behavior.

### Engineering

-   [ ] Unit tests cover boundaries, missing ranges, invalid intervals,
    and unit mismatches.
-   [ ] API authorization and cross-user access tests pass.
-   [ ] OCR and extraction tests cover supported document types.
-   [ ] Citations are verified against stored sources.
-   [ ] LangGraph failures and retries are bounded and tested.
-   [ ] CI runs deterministic and safety regression suites.
-   [ ] Logs and traces avoid unnecessary health information.
-   [ ] Backups, migrations, and deletion workflows are documented.

### Portfolio

-   [ ] README documents intended use and limitations.
-   [ ] Architecture, extraction, and safety diagrams are included.
-   [ ] Evaluation results are reported with dataset and pipeline
    versions.
-   [ ] Demo uses synthetic or properly de-identified reports.
-   [ ] Known limitations and future improvements are documented.
-   [ ] No claims of diagnostic accuracy or regulatory compliance are
    made without appropriate validation.

------------------------------------------------------------------------

## 20. Official Documentation and Trusted Starting Points

### Engineering documentation

-   **LangChain:**
    https://docs.langchain.com/oss/python/langchain/overview
-   **LangGraph:**
    https://docs.langchain.com/oss/python/langgraph/overview
-   **FastAPI:** https://fastapi.tiangolo.com/
-   **Next.js App Router:** https://nextjs.org/docs/app
-   **shadcn/ui:** https://ui.shadcn.com/docs
-   **DeepEval:** https://deepeval.com/docs/getting-started-rag
-   **LangSmith observability:**
    https://docs.langchain.com/langsmith/observability
-   **PostgreSQL:** https://www.postgresql.org/docs/
-   **pgvector:** https://github.com/pgvector/pgvector

### Example public health education sources to evaluate for an allowlist

-   **MedlinePlus:** https://medlineplus.gov/
-   **National Library of Medicine:** https://www.nlm.nih.gov/
-   **National Institutes of Health:** https://www.nih.gov/
-   **U.S. Centers for Disease Control and Prevention:**
    https://www.cdc.gov/

These are candidate sources, not a blanket approval of every page for
every medical claim. Curate and review the actual source corpus and
record provenance, licensing, update dates, and scope.

------------------------------------------------------------------------

## Final Recommendation

Build LabLens in this order:

**Secure ingestion → extraction review → deterministic range logic →
trusted-source RAG → LangGraph workflow → safety and evaluation →
production deployment.**

The defining engineering principle is separation of responsibilities:
code handles measured values and reference-range comparisons; approved
sources provide educational evidence; the LLM explains that evidence in
plain language; and deterministic validators enforce output and citation
contracts.

The application should help users understand the report and prepare for
a conversation with a clinician---not diagnose them or decide treatment.
