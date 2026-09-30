# Architecture & Engineering Decisions

Record meaningful technical decisions here.

## Decision Template

### DEC-XXX — Title
**Date:** YYYY-MM-DD
**Status:** Accepted / Superseded

**Context**
What problem required a decision?

**Decision**
What was chosen?

**Alternatives**
What other approaches were considered?

**Reason**
Why was the chosen approach selected?

**Consequences**
What does this decision make easier/harder?

---

## Current Decisions

### DEC-001 — Observation and Incident Are Separate Domain Entities
**Status:** Accepted

A raw observation/report remains separate from an incident. Multiple observations can belong to one incident.

**Reason:** The platform aggregates noisy reports into meaningful incidents while preserving evidence.

**Consequences:** The data model requires reports, incidents, and their relationships.

### DEC-002 — Demo/Replay Mode Is First-Class
**Status:** Accepted

The platform supports deterministic data replay/simulation.

**Reason:** External APIs may be unavailable, rate-limited, or unreliable during judging.

**Consequences:** Ingestion supports live connectors and replay/fixture adapters.

### DEC-003 — AI Confidence Is Not Official Truth
**Status:** Accepted

AI produces evidence/confidence assessments rather than absolute truth labels.

**Reason:** Reports are noisy and model outputs are probabilistic.

**Consequences:** The system distinguishes AI assessments from human verification.

### DEC-004 - Explicit Stream Transport (`STREAM_MODE`), No Silent Fallback
**Date:** 2026-09-30
**Status:** Accepted

**Context**
The producer originally attempted a live Redpanda publish and, on failure, silently fell back to an in-memory bus. The API then reported the observation as `ACCEPTED`/`PUBLISHED` even though nothing reached the broker — an unobservable data-loss path that also hides infrastructure outages during judging.

**Decision**
Introduce an explicit `STREAM_MODE` setting:
- `redpanda` — live broker is mandatory. Publish failures raise `StreamPublishError` and the API answers HTTP 503 with an explicit "NOT accepted" detail. Nothing is reported as successful.
- `bus` — deterministic in-memory transport used only by unit tests and local demo mode; readiness reports the streaming component as `degraded`.

Topics are bootstrapped at startup (`EventProducer.ensure_topics()`) so `weather.raw.v1` / `weather.dlq.v1` always exist when the broker is up.

**Alternatives**
1. Keep silent fallback with a log warning — rejected: hides data loss and produces fake success responses.
2. Remove the in-memory bus entirely — rejected: tests and demo mode need a deterministic, broker-free transport (DEC-002).
3. Retry indefinitely inside the request — rejected: unbounded request latency; the caller cannot distinguish "queued" from "lost".

**Reason**
Correctness and observability outrank availability of a single submission: a rejected submission is recoverable, a silently dropped observation is not.

**Consequences**
- Citizen submission can fail visibly during a broker outage (covered by `test_api_fails_clearly_when_redpanda_unavailable`).
- Tests must set `STREAM_MODE` explicitly; live tests override it to `redpanda`.
- `/ready` reports `degraded` in demo mode, so the deployment posture is always visible.

### DEC-005 - Reconcile the Live Schema With an Idempotent Migration
**Date:** 2026-09-30
**Status:** Accepted

**Context**
The live database was bootstrapped by `infra/init-db.sql` while Alembic had `001_initial_schema`. Running `alembic upgrade head` failed because the objects already existed, and `alembic stamp head` alone would have hidden real drift (missing `report_hash`, `processing_status`, `metadata_json`, no location trigger, no tracked geography reconciliation).

**Decision**
Add `002_reconcile_postgis_schema`, written to be idempotent: `IF NOT EXISTS` guards for columns/indexes/constraints, guarded conversion to `geography(Point,4326)`, creation of the `bwip_sync_location_column()` trigger with backfill, and FK/index checks. `001_initial_schema` is skipped when the schema already exists, and its `downgrade()` refuses to run unless `ALLOW_DESTRUCTIVE_DOWNGRADE=1`.

**Alternatives**
1. `alembic stamp head` without reconciliation — rejected: leaves genuine drift undocumented.
2. Drop and recreate the schema from Alembic — rejected: destructive migration requiring confirmation, and it destroys verification data.
3. Edit `init-db.sql` only — rejected: existing deployments would drift permanently.

**Reason**
Migrations are the source of truth going forward; the safest reversible path is additive reconciliation, not a rebuild.

**Consequences**
- `alembic current` reports `002_reconcile_postgis_schema (head)` and future migrations build on a truthful baseline.
- Re-running on a fresh or partially initialised database is safe.
- `init-db.sql` remains the fast bootstrap path for brand-new environments.
