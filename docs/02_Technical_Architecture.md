# National Weather Big Data Analytics Platform — Technical Architecture Document

**Version:** 1.0  
**Date:** 29 September 2026  
**Architecture style:** Event-driven, modular, geo-aware, AI-assisted, incident-centric

---

## 1. Architecture Principles

1. **Observation ≠ incident ≠ truth.** Preserve these concepts separately.
2. **API-first.** Frontend must not talk directly to databases or external providers.
3. **Event-driven ingestion.** Connectors publish canonical events; processors subscribe.
4. **Idempotent processing.** Replays must not create duplicate records.
5. **Raw + normalized + analytical layers.** Never destroy source provenance.
6. **Geo-aware by default.** Location is a first-class data type.
7. **Human-in-the-loop.** High-impact verification remains reviewable.
8. **Provider independence.** No single external AI/data provider should be a hard dependency.
9. **Explainability over magic.** Every confidence outcome exposes contributing signals.
10. **Progressive scale.** Start with a modular monolith + workers; split services only when load or ownership justifies it.

---

## 2. Logical Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                              │
│  Social APIs | Weather APIs | Public Data | Websites | Citizens    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER                             │
│ Connector Workers | Validation | Rate Limits | Source Adapters     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           REDPANDA                                   │
│ raw | normalized | classified | verified | incidents | alerts       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
        ┌──────────────────────┼───────────────────────────┐
        ▼                      ▼                           ▼
┌───────────────┐      ┌────────────────┐        ┌────────────────┐
│ Normalizer    │      │ NLP/AI workers │        │ Geo workers    │
│ schema/clean  │      │ classify/NLP   │        │ resolve/map    │
└───────┬───────┘      └────────┬───────┘        └───────┬────────┘
        └───────────────────────┼─────────────────────────┘
                                ▼
                     ┌────────────────────┐
                     │ Dedup / Clustering  │
                     └──────────┬─────────┘
                                ▼
                     ┌────────────────────┐
                     │ Verification Engine │
                     └──────────┬─────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                              STORAGE                                │
│ PostgreSQL/PostGIS | Redis | MinIO/Object Store | Parquet/Data Lake│
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
                     ┌────────────────────┐
                     │ Analytics / Spark  │
                     └──────────┬─────────┘
                                ▼
              ┌─────────────────┴──────────────────┐
              ▼                                    ▼
       ┌──────────────┐                      ┌──────────────┐
       │ Public/Admin │                      │ Observability│
       │ APIs + UI    │                      │ Prometheus   │
       └──────┬───────┘                      │ Grafana      │
              ▼                              └──────────────┘
       ┌──────────────┐
       │ Next.js Web  │
       └──────────────┘
```

---

## 3. Recommended Technology Stack

| Layer | MVP | Scale-out option |
|---|---|---|
| Web | Next.js + TypeScript | Same |
| Maps | MapLibre GL | Vector tiles / optimized geo services |
| API | FastAPI | Multiple API replicas |
| Database | PostgreSQL + PostGIS | Read replicas / partitioning |
| Queue | Redpanda | Multi-node Redpanda/Kafka |
| Cache | Redis | Redis cluster |
| Object store | MinIO | S3-compatible object storage |
| AI | Python workers + HF + selected LLM | GPU inference service |
| Batch | Python | PySpark |
| Monitoring | Prometheus + Grafana | Managed metrics/logging stack |
| Auth | JWT/OIDC abstraction | Enterprise IdP |
| Packaging | Docker Compose | Kubernetes |

---

## 4. Deployment Topology — Competition

```text
Internet
   │
   ▼
Reverse Proxy / HTTPS
   │
   ├────────► Next.js
   │
   └────────► FastAPI
                 │
                 ├── PostgreSQL/PostGIS
                 ├── Redis
                 ├── Redpanda
                 ├── MinIO
                 └── AI Worker(s)
```

All services should be private-networked except the reverse proxy/web/API endpoints that must be public.

---

## 5. Deployment Topology — Production Target

```text
                    Internet / Agency Network
                              │
                       WAF / Load Balancer
                              │
                  ┌───────────┴───────────┐
                  ▼                       ▼
              Web Tier                API Gateway
                                          │
             ┌────────────────────────────┼────────────────────┐
             ▼                            ▼                    ▼
        API Services               Stream Services        Admin APIs
             │                            │                    │
             └───────────────┬────────────┴────────────────────┘
                             ▼
                      Redpanda Cluster
                             │
           ┌─────────────────┼──────────────────┐
           ▼                 ▼                  ▼
      AI Workers       Geo/Clusterers      Alert Workers
           └─────────────────┼──────────────────┘
                             ▼
          ┌────────────────────────────────────┐
          │ PostgreSQL/PostGIS + Redis         │
          │ Object Storage + Data Lake         │
          └─────────────────┬──────────────────┘
                            ▼
                    Spark / Analytics
```

---

## 6. Canonical Observation Schema

```json
{
  "event_id": "uuid",
  "source": {
    "type": "citizen|social|weather_api|dataset|web",
    "name": "string",
    "external_id": "string"
  },
  "observed_at": "ISO-8601",
  "ingested_at": "ISO-8601",
  "content": {
    "text": "string|null",
    "language": "string|null",
    "translated_text": "string|null",
    "media": []
  },
  "location": {
    "latitude": 0.0,
    "longitude": 0.0,
    "city": "string|null",
    "district": "string|null",
    "state": "string|null",
    "provenance": "gps|user_selected|metadata|geocoded|weather_grid|unknown",
    "confidence": 0.0
  },
  "classification": {
    "event_type": "FLOOD",
    "confidence": 0.0
  },
  "privacy": {
    "contains_personal_data": false,
    "visibility": "internal|restricted|public_summary"
  },
  "raw_ref": "object://..."
}
```

---

## 7. Storage Model

### 7.1 PostgreSQL/PostGIS
Operational source of truth for:

- users
- roles
- reports
- incidents
- incident_reports
- event_predictions
- verification_results
- audit_logs
- connector_status
- model_registry

Use `geography(Point, 4326)` for point locations where appropriate.

### 7.2 Object store
Store:

- original media where retention is permitted
- thumbnails
- raw API responses where permitted
- replay datasets
- model artifacts (or a separate model registry)

### 7.3 Data lake
Partition analytical data by event date and optionally state/event type:

```text
lake/
  raw/date=YYYY-MM-DD/
  normalized/date=YYYY-MM-DD/
  incidents/date=YYYY-MM-DD/
```

Use Parquet for efficient analytical scans.

---

## 8. Core Tables

### reports

```sql
id UUID PRIMARY KEY
source_id UUID
external_id TEXT
text TEXT
language TEXT
observed_at TIMESTAMPTZ
ingested_at TIMESTAMPTZ
latitude DOUBLE PRECISION
longitude DOUBLE PRECISION
location GEOGRAPHY(Point,4326)
location_provenance TEXT
location_confidence NUMERIC
city TEXT
district TEXT
state TEXT
raw_object_key TEXT
created_at TIMESTAMPTZ
```

Recommended indexes:

```sql
CREATE INDEX reports_location_gix ON reports USING GIST (location);
CREATE INDEX reports_observed_at_idx ON reports (observed_at DESC);
CREATE INDEX reports_event_source_idx ON reports (source_id, observed_at DESC);
```

### incidents

```sql
id UUID PRIMARY KEY
title TEXT
event_type TEXT
severity TEXT
confidence NUMERIC
latitude DOUBLE PRECISION
longitude DOUBLE PRECISION
location GEOGRAPHY(Point,4326)
city TEXT
district TEXT
state TEXT
started_at TIMESTAMPTZ
last_updated_at TIMESTAMPTZ
status TEXT
observation_count INT
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

### verification_results

```sql
id UUID PRIMARY KEY
report_id UUID
source_score NUMERIC
content_score NUMERIC
location_score NUMERIC
temporal_score NUMERIC
weather_correlation_score NUMERIC
media_score NUMERIC
cross_report_score NUMERIC
duplicate_risk NUMERIC
overall_confidence NUMERIC
status TEXT
model_version TEXT
created_at TIMESTAMPTZ
```

---

## 9. Stream Topology

Topics:

```text
weather.raw.v1
weather.normalized.v1
weather.classified.v1
weather.geolocated.v1
weather.deduped.v1
weather.verified.v1
weather.incidents.v1
weather.alerts.v1
weather.dlq.v1
```

Event keys:

- Raw/normalized: `source + external_id` or event UUID.
- Incident events: incident UUID.
- Partitioning strategy should be revisited under production load.

### Delivery strategy

Target **at-least-once delivery** with idempotent consumers.

Every processing stage must safely re-run the same event.

---

## 10. Processing Pipeline

### Stage A — Ingestion

Connector responsibilities:

1. Fetch source data.
2. Validate source response.
3. Create canonical envelope.
4. Publish raw message.
5. Record cursor/checkpoint.

### Stage B — Normalization

- Unicode normalization.
- Timestamp normalization to UTC.
- Text cleanup.
- URL extraction.
- Media reference normalization.
- Source metadata normalization.

### Stage C — Language / NLP

- Detect language.
- Extract location entities.
- Extract weather event terms.
- Run event classifier.
- Optional LLM structured extraction.

### Stage D — Geolocation

Priority:

1. GPS coordinates.
2. Trusted structured location.
3. User-selected location.
4. Named location from text.
5. Weather grid coordinate.
6. Unknown.

### Stage E — Deduplication

Layers:

1. Exact external ID duplicate.
2. Exact text hash.
3. Media perceptual hash.
4. Semantic embedding similarity.
5. Geo-temporal proximity.

### Stage F — Incident clustering

Candidate criteria:

```text
same/compatible event type
AND
within spatial radius
AND
within time window
AND
semantic similarity above threshold
```

### Stage G — Corroboration

Fetch or reference supporting weather observations and nearby reports.

### Stage H — Incident update

Update aggregate values and publish an incident event.

---

## 11. Deduplication Design

### Exact duplicate

```text
hash(source + external_id) → same report
```

### Near-duplicate text

Use normalized text hash plus token similarity.

### Semantic duplicate

Generate an embedding for the report content.

Example feature set:

```text
semantic_similarity
geo_distance
time_distance
same_event_type
media_similarity
```

Example weighted candidate score:

```text
candidate =
  0.45 * semantic_similarity
+ 0.25 * geo_similarity
+ 0.20 * time_similarity
+ 0.10 * event_similarity
```

Thresholds must be calibrated on labeled data rather than assumed to be universally correct.

---

## 12. Incident Clustering

A simple MVP method:

1. Search incidents within geographic radius.
2. Restrict to time window.
3. Filter event compatibility.
4. Compute composite similarity.
5. Attach to best incident if above threshold.
6. Otherwise create a new incident.

Production evolution path:

- HDBSCAN/DBSCAN for spatial-temporal clustering.
- Stream clustering with sliding windows.
- Graph-based incident linking.

---

## 13. AI Architecture

AI tasks should be modular.

```text
Task                     Model type
------------------------------------------------
Language detection       lightweight classifier
Event classification     fine-tuned NLP or multilingual model
Entity extraction        NER/LLM
Translation              translation model/API
Embeddings               multilingual embedding model
Media evidence           CV classifier/object detector
Summarization            LLM with structured output
```

### LLM guardrails

LLM outputs must be schema-validated.

Never allow free-form model output to directly mutate database state.

Use:

```text
JSON schema validation
confidence bounds
prompt versioning
model versioning
fallback behavior
human review for privileged actions
```

---

## 14. Verification Engine

Input features:

```text
source_score
content_score
location_score
temporal_score
weather_correlation
media_score
cross_report_score
duplicate_risk
```

Output:

```json
{
  "overall_confidence": 0.86,
  "status": "AI_CORROBORATED",
  "reasons": [
    "Weather conditions are consistent",
    "Multiple nearby independent observations exist",
    "Location confidence is high"
  ],
  "model_version": "verify-1.0"
}
```

The UI must show supporting reasons rather than only a number.

---

## 15. API Architecture

Base path:

```text
/api/v1
```

### Public/read APIs

```http
GET /incidents
GET /incidents/{incident_id}
GET /reports/{report_id}
GET /analytics/summary
GET /analytics/timeline
GET /analytics/hotspots
GET /states/{state}/incidents
```

### Citizen APIs

```http
POST /citizen/reports
POST /citizen/reports/{id}/media
```

### Admin APIs

```http
POST /admin/reports/{id}/verify
POST /admin/reports/{id}/reject
POST /admin/reports/{id}/unconfirm
POST /admin/incidents/{id}/merge
POST /admin/incidents/{id}/split
PATCH /admin/incidents/{id}
GET /admin/review-queue
GET /admin/audit-logs
```

### System APIs

```http
GET /health
GET /ready
GET /metrics
```

---

## 16. Real-Time Delivery

Use WebSocket or Server-Sent Events.

Example WebSocket messages:

```json
{
  "type": "INCIDENT_CREATED",
  "incident": {
    "id": "...",
    "event_type": "FLOOD",
    "state": "Telangana",
    "city": "Hyderabad"
  }
}
```

Client behavior:

1. Receive event.
2. Update local query cache.
3. Update marker/cluster.
4. Update summary cards.
5. Animate only when useful; avoid distracting the analyst.

---

## 17. Caching

Redis cache keys:

```text
analytics:summary:{filters_hash}
analytics:timeline:{filters_hash}
incidents:nearby:{geohash}:{time_bucket}
incident:{id}
```

Use short TTLs for live dashboard aggregates.

Invalidate or version caches when incident state changes.

---

## 18. Batch Analytics / Big Data Path

```text
Postgres/object store
        ↓
Export normalized data to Parquet
        ↓
PySpark
        ↓
Aggregate by day/state/event
        ↓
Write analytical tables
        ↓
Dashboard analytics API
```

This establishes a clear distinction between:

- real-time operational processing, and
- historical large-scale analytics.

---

## 19. Failure Handling

### Retryable errors

- rate limit
- temporary network error
- transient DB error
- provider timeout

Use exponential backoff.

### Non-retryable errors

- invalid payload schema
- unsupported data type
- malformed coordinates
- corrupted media

Send to `weather.dlq.v1` and record diagnostics.

### Provider outage

- mark connector unhealthy
- stop aggressive retries
- preserve last successful cursor/checkpoint
- continue other pipelines
- notify operations

---

## 20. Observability

Metrics:

```text
ingestion_events_total
processing_events_total
processing_errors_total
consumer_lag
api_request_duration_seconds
ai_inference_duration_seconds
reports_created_total
incidents_created_total
duplicate_reports_total
verification_actions_total
```

Logs must be structured JSON and include a correlation/request ID.

Tracing can be introduced after MVP with OpenTelemetry.

---

## 21. Security Architecture Overview

```text
Browser
  ↓ HTTPS
WAF/Reverse Proxy
  ↓
API Gateway
  ↓ JWT/OIDC + RBAC
Application services
  ↓ network policies
Postgres / Redis / Object Store
```

Security requirements are defined in the Security & Access document.

---

## 22. Scaling Strategy

### First bottleneck: ingestion
Scale connector workers horizontally.

### Second bottleneck: AI
Separate inference workers and use queues; batch embeddings.

### Third bottleneck: geo queries
Use PostGIS GiST indexes, pre-aggregation, and caching.

### Fourth bottleneck: map rendering
Server-side clustering and vector tiles if required.

### Fifth bottleneck: historical analytics
Move heavy scans to Parquet/Spark.

---

## 23. Architectural Tradeoffs

### Why PostgreSQL + PostGIS?

One operational database can handle relational state and spatial queries without introducing a second geo database in the MVP.

### Why Redpanda/Kafka-compatible streaming?

It cleanly decouples connectors from processors and demonstrates a credible streaming architecture.

### Why MinIO/object storage?

Media and raw payloads should not live directly in PostgreSQL.

### Why not microservices from day one?

Too many service boundaries increase deployment and debugging cost before there is enough load or organizational separation to justify them.

### Why Python for AI/backend workers?

The AI/data ecosystem is strongest in Python and integrates well with FastAPI, ML libraries, and Spark.

---

## 24. Repository Architecture

```text
/apps
  /web
  /api
/services
  /ingestion
  /processing
  /verification
  /analytics
/ml
/infra
/scripts
/tests
/docs
```

Keep each package independently testable.

---

## 25. CI/CD

Pipeline:

```text
Pull Request
 ↓
lint
 ↓
type check
 ↓
unit tests
 ↓
API tests
 ↓
security/dependency scan
 ↓
build containers
 ↓
integration tests
 ↓
deploy staging
```

For the competition, a single protected main branch plus automatic preview deployment is sufficient.

---

## 26. Architecture Decision Records

Create ADRs for:

- ADR-001 streaming platform choice.
- ADR-002 relational/geo storage.
- ADR-003 LLM usage boundaries.
- ADR-004 incident-centric data model.
- ADR-005 source retention/licensing.
- ADR-006 authentication/identity provider.
- ADR-007 public vs restricted media storage.

---

## 27. Technical Acceptance Criteria

- Every source connector outputs the canonical schema.
- Reprocessing an event does not create duplicate incidents.
- All location points are stored with provenance.
- AI model versions are persisted with predictions.
- Verification is reproducible from stored evidence signals.
- Incident clustering is deterministic for the same input/configuration.
- API responses have stable versioned schemas.
- Database geo queries use spatial indexes.
- Streaming failures route to a DLQ.
- Dashboard can recover from WebSocket reconnect.
- All privileged mutations emit audit logs.

---

## 28. External Reference Sources

- IMD: https://mausam.imd.gov.in/
- CERT-In: https://www.cert-in.org.in/
- CERT-In guidelines: https://www.cert-in.org.in/s2cMainServlet?pageid=GUIDLNVIEW01
- X developer docs: https://developer.x.com/
- PostGIS: https://postgis.net/documentation/
- Redpanda: https://docs.redpanda.com/

---
