# National Weather Big Data Analytics Platform — Feature Ticket List

**Version:** 1.0  
**Date:** 29 September 2026  
**Board style:** Epic → Feature → Task  
**Priority:** P0 = must have, P1 = important, P2 = stretch

---

## 1. Delivery Strategy

Build in vertical slices rather than by department:

```text
Source → Stream → Process → Incident → API → UI → Review
```

Each slice should reach demoable functionality.

---

## 2. Definition of Done — Global

A ticket is Done when:

- code is merged
- automated tests exist for important paths
- errors are handled
- logging/metrics exist where relevant
- security impact is reviewed
- API/schema changes are documented
- UI states cover loading/error/empty cases where applicable
- acceptance criteria pass

---

# EPIC E-01 — Project Foundation

## NW-001 Repository bootstrap
**Priority:** P0  
**Estimate:** 0.5 day

**Scope**

Create monorepo structure, README, environment conventions, commit hooks, and docs folder.

**Acceptance**
- repository builds
- `.env.example` exists
- services have basic health checks

## NW-002 Docker Compose infrastructure
**Priority:** P0  
**Estimate:** 1 day

Services:

- web
- api
- postgres
- redpanda
- redis
- minio

**Acceptance**
- `docker compose up` starts all MVP services
- persistent volumes configured

## NW-003 PostgreSQL + PostGIS setup
**Priority:** P0  
**Estimate:** 0.5 day

**Acceptance**
- extension enabled
- migrations run
- spatial index tested

## NW-004 CI pipeline
**Priority:** P0  
**Estimate:** 1 day

Lint, tests, type checks, container build.

## NW-005 Secrets/config management
**Priority:** P0  
**Estimate:** 0.5 day

**Acceptance**
- secrets absent from Git
- `.env.example` documents required variables

---

# EPIC E-02 — Identity & Access

## NW-010 Authentication foundation
**P0 / 1 day**

Implement OIDC/JWT-based authentication abstraction.

## NW-011 RBAC middleware
**P0 / 1 day**

Roles: analyst, reviewer, admin, platform admin.

## NW-012 Object-level authorization tests
**P0 / 0.5 day**

Test BOLA/IDOR scenarios.

## NW-013 Admin MFA configuration
**P0 / 0.5–1 day**

Use identity provider capability; don't build custom MFA unless necessary.

---

# EPIC E-03 — Canonical Data Model

## NW-020 Reports schema
**P0 / 1 day**

Create report model and migrations.

## NW-021 Incidents schema
**P0 / 0.5 day**

Create incident + association tables.

## NW-022 Verification schema
**P0 / 0.5 day**

Store evidence signals, confidence, model version.

## NW-023 Audit log schema
**P0 / 0.5 day**

Append-only design.

## NW-024 OpenAPI schema publication
**P0 / 0.5 day**

Publish versioned API docs.

---

# EPIC E-04 — Citizen Reporting

## NW-030 Citizen report API
**P0 / 1 day**

`POST /api/v1/citizen/reports`

## NW-031 Citizen report form
**P0 / 1 day**

Text, event type, location, media.

## NW-032 Media upload service
**P0 / 1 day**

Presigned/private upload to object storage.

## NW-033 Media validation/scanning
**P0 / 1 day**

File signature, size, MIME, antivirus scan.

## NW-034 Report confirmation page
**P1 / 0.25 day**

Reference ID and processing status.

---

# EPIC E-05 — External Data Ingestion

## NW-040 Connector interface
**P0 / 0.5 day**

Define `Connector` contract.

## NW-041 Weather API connector
**P0 / 1 day**

Ingest current/historical weather data through a supported API.

## NW-042 Social API connector
**P0 / 1–2 days**

Use only an authorized/permitted provider API and documented query rules.

## NW-043 Dataset import connector
**P0 / 0.5 day**

CSV/JSON/Parquet batch import.

## NW-044 Connector health/status
**P1 / 0.5 day**

Track last success, error rate, cursor/checkpoint.

## NW-045 Rate-limit and retry middleware
**P0 / 0.5 day**

Exponential backoff and provider-safe throttling.

---

# EPIC E-06 — Streaming

## NW-050 Redpanda topic bootstrap
**P0 / 0.5 day**

Create topic conventions and retention settings.

## NW-051 Raw event publisher
**P0 / 0.5 day**

Publish canonical raw event.

## NW-052 Normalizer consumer
**P0 / 1 day**

Normalize timestamps/text/metadata.

## NW-053 Dead-letter queue
**P0 / 0.5 day**

Route invalid events.

## NW-054 Idempotency layer
**P0 / 1 day**

Prevent replay duplication.

---

# EPIC E-07 — AI Event Classification

## NW-060 Event taxonomy
**P0 / 0.5 day**

Implement enum + display metadata.

## NW-061 Baseline classifier
**P0 / 1 day**

Rules + lightweight model.

## NW-062 LLM structured extraction
**P1 / 1 day**

Extract event, location cues, severity cues, entities.

## NW-063 Model registry
**P1 / 0.5 day**

Store model/version/prompt metadata.

## NW-064 Classification evaluation dataset
**P0 / 1 day**

Create manually labelled validation set.

## NW-065 Classification metrics job
**P1 / 0.5 day**

Precision, recall, F1 by class.

---

# EPIC E-08 — Geolocation

## NW-070 Location extraction
**P0 / 1 day**

NER/LLM extraction with structured output.

## NW-071 Geocoder adapter
**P0 / 1 day**

Provider abstraction + caching.

## NW-072 Location provenance
**P0 / 0.5 day**

Store source of coordinates and confidence.

## NW-073 Manual location correction
**P1 / 0.5 day**

Reviewer/admin map correction.

---

# EPIC E-09 — Deduplication

## NW-080 Exact duplicate detection
**P0 / 0.5 day**

Source ID/hash matching.

## NW-081 Semantic similarity service
**P0 / 1 day**

Generate embeddings.

## NW-082 Media perceptual hashing
**P1 / 0.5 day**

Detect recycled images.

## NW-083 Geo-temporal duplicate scoring
**P0 / 1 day**

Combine semantic/time/location signals.

## NW-084 Dedup evaluation dataset
**P0 / 1 day**

Label duplicates/non-duplicates.

---

# EPIC E-10 — Incident Clustering

## NW-090 Candidate incident search
**P0 / 0.5 day**

Nearby/time-window query using PostGIS.

## NW-091 Incident similarity score
**P0 / 0.5 day**

Semantic + geo + time + event.

## NW-092 Incident creation service
**P0 / 1 day**

Create new incident when no candidate qualifies.

## NW-093 Incident update service
**P0 / 1 day**

Update count/location/confidence/timeline.

## NW-094 Merge incidents
**P1 / 0.5 day**

Reviewer/admin action.

## NW-095 Split incidents
**P1 / 1 day**

Move selected observations.

---

# EPIC E-11 — Verification & Explainability

## NW-100 Weather corroboration service
**P0 / 1 day**

Compare report against nearby weather observation.

## NW-101 Source scoring
**P1 / 0.5 day**

Configurable reliability signals.

## NW-102 Media evidence model
**P1 / 1–2 days**

Image evidence classifier.

## NW-103 Cross-report corroboration
**P0 / 0.5 day**

Count independent nearby reports.

## NW-104 Confidence aggregation
**P0 / 1 day**

Produce score + reason codes.

## NW-105 Human verification workflow
**P0 / 1 day**

Verify/reject/unconfirm actions.

## NW-106 Verification explanation UI
**P0 / 0.5 day**

Evidence panel with reasons.

---

# EPIC E-12 — Public Dashboard

## NW-110 Dashboard shell
**P0 / 0.5 day**

Header, nav, page frame.

## NW-111 National India map
**P0 / 1 day**

MapLibre setup + incident markers.

## NW-112 Map clustering
**P0 / 1 day**

Cluster markers and viewport querying.

## NW-113 Global filters
**P0 / 1 day**

Date/state/city/event/status/severity.

## NW-114 Incident drawer
**P0 / 0.5 day**

Compact incident detail.

## NW-115 Incident detail page
**P0 / 1 day**

Timeline, evidence, reports, map.

## NW-116 KPI cards
**P0 / 0.5 day**

Counts and last-updated time.

## NW-117 Timeline chart
**P1 / 0.5 day**

Incidents by hour/day.

## NW-118 Event distribution chart
**P1 / 0.5 day**

Event mix.

---

# EPIC E-13 — Admin Panel

## NW-120 Review queue
**P0 / 1 day**

Priority-sorted table.

## NW-121 Review workspace
**P0 / 1 day**

Evidence + source + action layout.

## NW-122 Admin incident manager
**P1 / 1 day**

Merge/split/edit status.

## NW-123 User management
**P1 / 0.5 day**

Role assignment/deactivation.

## NW-124 Connector manager
**P1 / 1 day**

Enable/disable connectors, status.

## NW-125 Model manager
**P2 / 1 day**

Model version/prompts.

## NW-126 Audit log viewer
**P0 / 0.5 day**

Search/filter audit events.

---

# EPIC E-14 — Real-Time Delivery

## NW-130 WebSocket/SSE gateway
**P0 / 1 day**

## NW-131 Live incident updates
**P0 / 0.5 day**

## NW-132 Live summary card updates
**P1 / 0.5 day**

## NW-133 Reconnect/offline state
**P0 / 0.5 day**

---

# EPIC E-15 — Analytics

## NW-140 Analytics summary API
**P0 / 0.5 day**

## NW-141 Timeline analytics
**P0 / 0.5 day**

## NW-142 State/district aggregation
**P0 / 1 day**

## NW-143 Hotspot analytics
**P1 / 1 day**

## NW-144 Confidence analytics
**P1 / 0.5 day**

## NW-145 Verification funnel
**P1 / 0.5 day**

---

# EPIC E-16 — Big Data

## NW-150 Parquet export pipeline
**P1 / 1 day**

## NW-151 Data lake partitioning
**P1 / 0.5 day**

## NW-152 PySpark batch job
**P1 / 1–2 days**

## NW-153 Historical trend dataset
**P1 / 1 day**

---

# EPIC E-17 — Observability

## NW-160 Prometheus metrics
**P1 / 1 day**

## NW-161 Grafana dashboard
**P1 / 1 day**

## NW-162 Structured logging
**P0 / 0.5 day**

## NW-163 Connector health page
**P1 / 0.5 day**

---

# EPIC E-18 — Security Hardening

## NW-170 Dependency/secret scans
**P0 / 0.5 day**

## NW-171 DAST against staging
**P0 / 1 day**

## NW-172 Upload security tests
**P0 / 0.5 day**

## NW-173 Prompt-injection tests
**P0 / 0.5 day**

## NW-174 Rate-limit tests
**P0 / 0.5 day**

## NW-175 Backup/restore drill
**P1 / 0.5 day**

---

# EPIC E-19 — Demo Reliability

## NW-180 Simulation data generator
**P0 / 1 day**

Generate controlled observation streams.

## NW-181 Replay engine
**P0 / 1 day**

Replay at configurable events/sec.

## NW-182 Competition demo mode
**P0 / 0.5 day**

Visible SIMULATION banner.

## NW-183 Demo scenario seed
**P0 / 0.5 day**

Prepare one coherent flood/storm scenario.

## NW-184 Demo reset button
**P0 / 0.25 day**

Reset DB/data for repeated judging runs.

---

## 3. Recommended Sprint Plan

### Sprint 1 — Foundation + Citizen Slice

```text
NW-001 to NW-005
NW-010 to NW-013
NW-020 to NW-024
NW-030 to NW-033
```

Outcome:

```text
Citizen
 ↓
API
 ↓
Postgres
```

### Sprint 2 — Streaming Slice

```text
NW-040 to NW-045
NW-050 to NW-054
```

Outcome:

```text
Connector
 ↓
Redpanda
 ↓
Processor
 ↓
DB
```

### Sprint 3 — AI + Geo

```text
NW-060 to NW-065
NW-070 to NW-073
```

### Sprint 4 — Dedup + Incident

```text
NW-080 to NW-084
NW-090 to NW-095
```

### Sprint 5 — Verification + Dashboard

```text
NW-100 to NW-106
NW-110 to NW-118
```

### Sprint 6 — Admin + Real-Time

```text
NW-120 to NW-126
NW-130 to NW-133
```

### Sprint 7 — Analytics + Big Data + Observability

```text
NW-140 to NW-145
NW-150 to NW-153
NW-160 to NW-163
```

### Sprint 8 — Security + Demo

```text
NW-170 to NW-175
NW-180 to NW-184
```

---

## 4. Parallel Work Streams

For a 4-person team:

```text
Person A — Backend/API/DB
Person B — AI/Data pipeline
Person C — Frontend/Map/Admin
Person D — Infra/Security/Integration
```

For a 3-person team:

```text
Person A — Backend + DB + streaming
Person B — AI + verification
Person C — Frontend + admin + demo
```

For a 2-person team:

```text
Person A — backend + AI
Person B — frontend + infrastructure
```

---

## 5. Critical Path

```text
Database
  ↓
Canonical schema
  ↓
Streaming
  ↓
Normalization
  ↓
AI classification + geolocation
  ↓
Deduplication
  ↓
Incident clustering
  ↓
Verification
  ↓
API
  ↓
Dashboard
  ↓
Admin
```

Do not build analytics dashboards before the incident data model works.

---

## 6. Ticket Priority Rules

### P0
Required to demonstrate the core problem statement.

### P1
Significantly strengthens the product but can ship after MVP.

### P2
Stretch; do only if the critical path is stable.

---

## 7. Release Checklist

### Core

- [ ] citizen report works
- [ ] external data connector works
- [ ] stream works
- [ ] report processing works
- [ ] incidents are created
- [ ] verification works
- [ ] live dashboard works
- [ ] admin review works

### Quality

- [ ] automated tests
- [ ] error states
- [ ] logs
- [ ] health checks
- [ ] security checks

### Demo

- [ ] simulation mode
- [ ] demo dataset
- [ ] reset workflow
- [ ] fallback if external API fails
- [ ] stable seeded scenario

---

## 8. Suggested GitHub Issue Labels

```text
priority:p0
priority:p1
priority:p2
area:frontend
area:backend
area:ai
area:data
area:infra
area:security
area:docs
bug
blocked
needs-review
hackathon-demo
```

---

## 9. Recommended First 10 Tickets to Execute

1. NW-001 Repository bootstrap
2. NW-002 Docker Compose infrastructure
3. NW-003 PostgreSQL + PostGIS
4. NW-020 Reports schema
5. NW-021 Incidents schema
6. NW-030 Citizen report API
7. NW-031 Citizen report form
8. NW-040 Connector interface
9. NW-050 Redpanda topic bootstrap
10. NW-051 Raw event publisher

At the end of this slice, you should have the foundation for a real vertical data path rather than isolated mockups.

---
