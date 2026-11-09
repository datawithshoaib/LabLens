# LabLens

LabLens helps people review the numbers and reference intervals printed on a laboratory report and prepare questions for a clinician. It is an educational tool: it does not diagnose conditions, recommend treatment, or replace medical care.

## What works today

- OIDC sign-in for a configured identity provider, plus a development-only local sign-in.
- Owner-scoped report upload, listing, download, and deletion.
- Private local or S3-compatible object storage, size/type limits, and per-user upload quotas.
- Durable PostgreSQL processing jobs dispatched through Redis to a separate worker.
- PDF page-count and encrypted-file inspection with bounded processing.
- Manual entry, correction, and confirmation of results. Confirmed numeric results use deterministic comparison against the interval the user entered.
- Audit events for report and result actions, readiness checks, security headers, and production configuration guards.

**Extraction and explanations are not implemented.** The worker checks a document and then asks the user to enter results manually. LabLens does not run OCR, extract tables, retrieve health sources, or generate AI explanations. Do not present this build as a clinically validated or publicly launched medical product.

## Run locally

Prerequisites: Docker Desktop with Compose.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Open `http://localhost:3000`. The API is bound to `http://localhost:8000`; its interactive API documentation is enabled in development at `/docs`. Local credentials are available only when `APP_ENV=development`. The example secrets are for local use and must never be reused for a deployment.

To run the web app or API outside Compose, use Node.js 24 and Python 3.12 with `npm ci` and `uv sync --project backend`, then set the local environment values from `.env.example`.

## Deployment shape

The containers are provider-neutral. Run the Next.js web service, FastAPI API, and ARQ worker as separate services; supply managed PostgreSQL, Redis, and private S3-compatible object storage. Terminate TLS at the deployment ingress, configure exact public origins and hostnames, and inject secrets through the platform's secret manager. Configure PostgreSQL with `ssl=require`, Redis URLs with TLS (`rediss://`), exact HTTPS origins, and private object storage. Configure OIDC issuer, API audience, JWKS URL, client credentials, HTTPS token endpoint, and a scope that issues refresh tokens. Set `AUTH_REDIS_URL` to a protected Redis connection; use TLS (`rediss://`). Rotating `AUTH_SECRET` invalidates existing sessions and requires users to sign in again.

See [docs/architecture.md](docs/architecture.md), [docs/privacy.md](docs/privacy.md), [docs/safety.md](docs/safety.md), and [docs/production-readiness.md](docs/production-readiness.md) before deploying.

## Repository map

- `backend/src/lablens/domain`: deterministic range comparison.
- `backend/src/lablens/api`: API contracts, health endpoints, report and result workflows.
- `backend/src/lablens/worker.py`: durable job dispatch and bounded document inspection.
- `backend/src/lablens/db` and `backend/alembic`: database models and migrations.
- `apps/web`: Next.js application, OIDC sign-in, and same-origin API proxy.
- `docs`: architecture, safety, privacy, and release boundaries.

Do not use identifiable health reports in development or evaluation without an approved privacy design and appropriate consent. Security controls do not by themselves establish HIPAA, GDPR, or other regulatory compliance.
