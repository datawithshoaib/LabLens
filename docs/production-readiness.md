# Production readiness

The repository now has a production-oriented service foundation, but it is not ready to accept real patient data or to launch publicly. This document separates implemented controls from deployment and product gates that require additional engineering or external review.

## Implemented in this repository

- Separate web, API, and worker containers; non-root runtime users; read-only container filesystems where supported; bounded upload body/file size and PDF page count.
- OIDC sign-in boundary with API JWT verification, owner-scoped report access, same-origin BFF checks, development-only local authentication, and provider-neutral configuration.
- Opaque browser sessions with encrypted server-side access/refresh tokens in Redis; token refresh and sign-out cleanup.
- PostgreSQL schema and Alembic migration; durable job rows, Redis dispatch, bounded retries, audit events, readiness checks, and asynchronous deletion.
- Private object storage abstraction, API security headers, allowed-host/CORS configuration, strict request schemas, and conservative health-related copy.
- No report-content logging, external OCR, external AI, or analytics integration.

## Required before any real-patient pilot

- Configure the actual OIDC provider, signed API-audience JWT access tokens, refresh-token policy, TLS endpoints, and deployment secrets; conduct an external security review of the identity and session flow.
- Use managed PostgreSQL, Redis, and private encrypted object storage with least-privilege credentials, tested backup/restore, defined backup expiration, monitoring, alerting, and incident procedures.
- Establish retention and deletion guarantees across live data, failed jobs, backups, audit records, and OIDC sessions. Monitor and remediate failed deletion jobs.
- Implement actual extraction/OCR only with page provenance, confidence signaling, bounded resource use, user correction, and evaluation. Until then, users must enter report values manually.
- Define the clinical safety case, approved source registry, privacy/legal review, consent, data processing agreements, intended-use boundaries, and jurisdiction-specific regulatory position.
- Add CI release gates for lint, type checks, dependency and container vulnerability scanning, migration review, and automated unit/integration/API/security/evaluation suites. These checks have not been run as part of the current change.
- Perform a deployment-specific threat model, load and failure testing, backup restoration drill, migration/rollback rehearsal, accessibility review, and clinical review.

## Required before explanations

- Select and contract with a provider only after privacy/security review of its data flow and terms.
- Curate/version trusted educational sources, retain source/page provenance, and validate every displayed citation.
- Generate explanations only from confirmed data and approved retrieved passages. Add deterministic output safety validation and clinical evaluation before enabling the feature.

Passing software checks does not establish clinical validity, diagnostic accuracy, privacy-law compliance, or regulatory clearance. Until the open gates above are completed, use synthetic data only and keep public access disabled.
