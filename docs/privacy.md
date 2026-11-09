# Privacy and data handling

This application now accepts and stores health reports. Treat uploaded bytes, extracted/entered values, and related metadata as sensitive health information.

## Current data flows

- The browser sends report files to the same-origin Next.js proxy. The proxy forwards them to the API and does not persist them.
- The API stores original files in local private filesystem storage for development or private S3-compatible storage when configured. PostgreSQL stores metadata, user association, entered results, processing state, and audit events.
- Redis holds job state and encrypted OIDC access/refresh token records. Auth.js browser cookies contain only an opaque session reference and are protected by Auth.js encryption and HttpOnly cookie settings.
- The current report worker reads file bytes only to validate document properties. There is no OCR service, analytics, tracing, or LLM provider integration.
- API errors avoid request contents and credentials. The report checksum is stored for integrity; it is not a substitute for access control.

## Deletion and retention

Users can request deletion. The record is hidden immediately and an asynchronous job removes the stored object and cascades related rows. Operational policy must set retention for report data, audit events, Redis sessions, backups, and failed deletion jobs. Backup copies can outlive the live record; disclose and enforce backup expiration before accepting real users. Alert on failed deletion jobs and provide a documented manual recovery process.

## Deployment requirements

Use TLS for browser/API and networked Redis/object storage connections, managed encrypted storage, least-privilege service credentials, a secret manager, restricted database access, short-lived sessions, access logging, redacted observability, dependency/image scanning, tested backup restoration, and a security incident process. Never log report contents, result values, tokens, or raw authentication headers. Do not place report bytes in public object URLs.

Do not use real health reports for development, demos, or evaluations without an approved privacy design and appropriate consent. Do not claim HIPAA, GDPR, or other compliance based on these technical controls. Requirements depend on jurisdiction, intended use, organizational role, contracts, and actual data flows; obtain qualified privacy and legal review.
