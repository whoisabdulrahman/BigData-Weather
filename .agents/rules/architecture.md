---
trigger: always_on
description: "Core architecture and domain invariants for the National Weather Platform"
---

# Architecture Rules

Follow:
@docs/02_Technical_Architecture.md
@docs/01_PRD.md

Core invariant:
**Observation/Report != Incident.**

Canonical flow:
DATA SOURCE → INGESTION → NORMALIZATION → CLASSIFICATION → GEOLOCATION → DEDUPLICATION → CORROBORATION → INCIDENT CLUSTERING → INCIDENT → ANALYTICS/DASHBOARD

Do not bypass this flow without documenting the reason in `docs/DECISIONS.md`.

Prefer existing architecture over new infrastructure.
Do not add a new database, framework, queue, cloud provider, or major architecture pattern without a documented reason.
Keep frontend, API, ingestion, processing, AI, incident engine, analytics, and infrastructure separate.
Prefer incremental changes over rewrites.
