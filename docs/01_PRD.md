# National Weather Big Data Analytics Platform — Product Requirements Document

**Product:** National Weather Big Data Analytics Platform (working name: **Bharat Weather Intelligence Platform / BWIP**)
**Organization:** Ministry of Earth Sciences (MoES)
**Department:** India Meteorological Department (IMD)
**Theme:** Disaster Management
**Category:** Software
**Document status:** Competition-ready baseline PRD
**Version:** 1.0
**Date:** 29 September 2026

---

## 1. Executive Summary

BWIP is a national-scale weather intelligence platform that ingests heterogeneous weather observations from permitted internet-based sources, public datasets/APIs, and citizen reports; transforms raw observations into normalized, geolocated, classified, deduplicated, and corroborated records; clusters related observations into **weather incidents**; and presents the resulting intelligence through a real-time web dashboard and an operational Admin Panel.

The platform is explicitly designed to separate **observation**, **AI inference**, and **human verification**:

- A social-media post or citizen report is an **observation**, not a fact.
- AI models produce classifications, extraction, similarity, and confidence signals.
- The verification engine combines independent evidence.
- Authorized human reviewers can verify or reject reports/incidents.
- The platform maintains an audit trail so decisions can be explained later.

### Core product thesis

> **Turn fragmented weather observations into geospatially clustered, explainable, evidence-backed weather incidents.**

---

## 2. Problem Statement

Weather information is distributed across social platforms, public data sources, websites, APIs, observational systems, and citizen channels. These sources vary in structure, quality, timeliness, reliability, language, and geographic precision.

The platform must support:

1. Near-real-time ingestion of weather-related information.
2. Centralized storage of raw and processed data.
3. AI-assisted event extraction and classification.
4. Identification of misleading, duplicated, stale, or weakly supported reports.
5. Automatic grouping of multiple observations into incidents.
6. Geospatial and time-based analytics.
7. Operational visualization for monitoring and manual verification.
8. Large-scale historical analytics.

---

## 3. Goals

### G1 — Unified ingestion
Create a connector architecture capable of ingesting data from multiple permitted sources behind a common schema.

### G2 — Real-time intelligence
Process new observations with low latency and surface meaningful changes without requiring page refresh.

### G3 — Event intelligence
Identify rainfall, thunderstorm, flooding, heatwave, fog, dust storm, and strong-wind events, while allowing the taxonomy to expand.

### G4 — Evidence-based verification
Produce transparent confidence signals from source, content, location, time, weather, media, and cross-report evidence.

### G5 — Incident-centric model
Cluster many observations into a smaller number of incidents to reduce noise and duplicate counting.

### G6 — Operational dashboard
Give analysts an India-wide map, filters, analytics, incident details, and review workflows.

### G7 — Scalable data platform
Support both streaming and batch workloads and demonstrate a credible path from prototype to large-scale deployment.

### G8 — Security and governance
Use least privilege, strong access control, auditability, data minimization, secure media handling, and source-specific access controls.

---

## 4. Non-Goals for Competition MVP

The following are intentionally out of scope for the first competition release:

- Automated issuance of official government warnings.
- Replacing IMD forecasting or official observation systems.
- Autonomous emergency dispatch.
- Guaranteed truth/falsity classification of user-generated content.
- Nationwide support for every social platform.
- Full production-grade Kubernetes orchestration.
- Training foundation models from scratch.
- Facial recognition or identity profiling of citizen reporters.
- Collecting unnecessary personally identifiable information.

These can be future phases after appropriate authorization, governance, and model validation.

---

## 5. Target Users

### 5.1 Public Viewer
Purpose: understand current incident activity and trends.

Capabilities:
- View national map.
- Filter incidents.
- Open incident details.
- See source categories and evidence summaries.
- See clearly labelled AI confidence and human verification status.

### 5.2 Analyst / Operations User
Purpose: investigate and correlate events.

Capabilities:
- Advanced filters.
- Time-series analytics.
- Geo-spatial exploration.
- Evidence inspection.
- Incident comparison.
- Export filtered data where authorized.

### 5.3 Reviewer / Admin
Purpose: validate reports and manage incidents.

Capabilities:
- Review queue.
- Verify/reject/unconfirm reports.
- Merge/split incidents.
- Correct classification/location.
- Review model explanations.
- See audit history.

### 5.4 Platform Administrator
Purpose: manage the system itself.

Capabilities:
- User and role management.
- Connector configuration.
- Model version configuration.
- Rate limits.
- System health.
- Audit and security events.

---

## 6. Core Concepts

### Observation
A single source item such as a social post, API observation, dataset row, or citizen report.

### Evidence
A signal used to support or challenge an observation: weather data, media analysis, nearby independent reports, source history, location consistency, etc.

### Incident
A time-and-location-bounded cluster of related observations describing a potential weather event.

### Confidence
An analytical score representing how strongly the available evidence supports an interpretation. It is not a legal or scientific declaration of truth.

### Human verification
An authorized reviewer outcome, separate from model confidence.

---

## 7. Functional Requirements

### FR-01 — Source ingestion
The platform shall ingest from a connector abstraction supporting:

- Social media APIs where permitted.
- Weather APIs.
- Public datasets.
- Website/RSS sources where permitted.
- Citizen report API.
- Batch import files.

Each connector must emit the canonical observation schema.

### FR-02 — Raw data preservation
The platform shall retain raw source payloads separately from normalized fields, subject to source licensing, retention policy, and privacy rules.

### FR-03 — Metadata extraction
The system shall capture or infer, when available:

- Timestamp.
- Source.
- Source item ID.
- Text.
- Media references.
- City/state/district.
- Latitude/longitude.
- Location confidence and provenance.
- Language.
- Event category.

### FR-04 — Event classification
The system shall classify observations into a controlled event taxonomy.

MVP classes:

- RAINFALL
- THUNDERSTORM
- FLOOD
- HEATWAVE
- FOG
- DUST_STORM
- STRONG_WIND
- OTHER/UNKNOWN

### FR-05 — Language detection
The platform shall identify source language and preserve original text. Translations, where used, shall be stored separately.

### FR-06 — Location resolution
The platform shall resolve explicit GPS first, user-selected location second, structured metadata third, and text-based geocoding only as a lower-confidence fallback.

### FR-07 — Deduplication
The platform shall identify exact, near-exact, media-level, and semantic duplicates.

### FR-08 — Incident clustering
The system shall cluster observations using temporal, geospatial, event-type, and semantic signals.

### FR-09 — Evidence aggregation
The system shall calculate corroboration signals using independent sources such as weather observations, multiple nearby reports, and media evidence where available.

### FR-10 — Verification workflow
Authorized reviewers shall be able to mark a report as:

- PENDING
- AI_CORROBORATED
- AI_FLAGGED
- HUMAN_VERIFIED
- HUMAN_REJECTED
- UNCONFIRMED

### FR-11 — Incident lifecycle
Incidents shall support:

- OPEN
- MONITORING
- VERIFIED
- RESOLVED
- ARCHIVED

### FR-12 — Real-time UI
New incidents and material incident changes shall be pushed to subscribed dashboard clients over a real-time channel such as WebSocket/SSE.

### FR-13 — Dashboard filtering
The dashboard shall support filtering by:

- Date/time range.
- State.
- District.
- City.
- Event type.
- Severity.
- Verification status.
- Source type.
- Confidence band.

### FR-14 — Analytics
The platform shall expose:

- Incident counts.
- Observation counts.
- Event distribution.
- Time trends.
- Geographic density.
- Source distribution.
- Verification status distribution.
- Confidence distribution.
- Processing latency.

### FR-15 — Admin review
The Admin Panel shall show a review queue with evidence and action controls.

### FR-16 — Audit trail
All privileged actions affecting reports, incidents, users, connectors, or model configuration shall be recorded.

### FR-17 — Export
Authorized users shall be able to export filtered observations/incidents to CSV/JSON; larger analytical exports may be asynchronous.

### FR-18 — Simulation/demo mode
The platform shall support replaying a prepared dataset into the streaming pipeline for judging/demo reliability.

---

## 8. Incident Intelligence Workflow

```text
Observation
   ↓
Normalize
   ↓
Language + entity extraction
   ↓
Location resolution
   ↓
Event classification
   ↓
Exact/semantic deduplication
   ↓
Nearby/time-window candidate search
   ↓
Incident clustering
   ↓
Cross-source corroboration
   ↓
Confidence + severity signals
   ↓
Human review where required
   ↓
Dashboard / alerts / analytics
```

---

## 9. Verification Model

### 9.1 Evidence dimensions

| Signal | Description |
|---|---|
| Source reliability | Historical source quality and platform-level signals |
| Content confidence | NLP/event classification confidence |
| Location confidence | Precision and provenance of the location |
| Temporal consistency | Whether time is compatible with evidence |
| Weather correlation | Agreement with independent weather observations |
| Media evidence | Whether media is semantically consistent with event type |
| Cross-report agreement | Independent nearby reports supporting the same event |
| Duplicate risk | Probability that the item is recycled/copied |

### 9.2 Confidence categories

| Score | UI interpretation |
|---:|---|
| 0.00–0.29 | Low corroboration |
| 0.30–0.59 | Limited corroboration |
| 0.60–0.79 | Moderate corroboration |
| 0.80–1.00 | Strong corroboration |

These are product thresholds for triage, not official IMD classifications.

---

## 10. Severity Model

MVP severity:

- LOW
- MEDIUM
- HIGH
- CRITICAL

Severity inputs may include:

- Incident type.
- Number of independent observations.
- Geographic spread.
- Weather intensity signals.
- Persistence/duration.
- Media evidence.
- Confidence.

The platform shall label this as an **analytical severity**, not an official government warning level.

---

## 11. Non-Functional Requirements

### Performance

- API p95 read latency target: < 500 ms for common dashboard queries.
- Common write acknowledgement: < 1 s under MVP load.
- Target end-to-end observation-to-dashboard latency: < 10 s for routine events.
- Map interactions should remain responsive with clustered rendering.

### Availability

- MVP target: 99% during judging periods.
- Production architecture target: 99.9%+, subject to infrastructure.

### Scalability

The architecture shall support independent horizontal scaling of:

- Ingestion workers.
- Stream processors.
- AI workers.
- API servers.
- WebSocket gateways.
- Batch analytics workers.

### Reliability

- At-least-once ingestion with idempotent processing.
- Retry with exponential backoff.
- Dead-letter queue for poison messages.
- Replayable raw events.

### Observability

Track:

- Event throughput.
- Consumer lag.
- Processing latency.
- API latency.
- AI latency.
- Error rate.
- Connector health.
- Queue depth.
- Database health.

### Accessibility

Target WCAG 2.2 AA practices for primary UI workflows where practical.

---

## 12. Data Retention Principles

Retention must be configurable by source class and purpose.

Recommended competition defaults:

- Raw social payloads: shortest practical retention consistent with source terms.
- Citizen personal data: minimized and short-lived unless needed for an active investigation or authorized purpose.
- Normalized weather observations: longer analytical retention.
- Aggregated incident statistics: long retention.
- Audit logs: retained according to security/governance requirements.

---

## 13. Privacy-by-Design Requirements

- Do not require citizen name or phone unless operationally necessary.
- Support anonymous reporting for the MVP.
- Collect precise GPS only when needed and with user awareness.
- Redact unnecessary personal data from analyst views.
- Separate source identity from public incident summaries where possible.
- Protect media URLs behind authorization when the media is non-public.
- Support deletion/retention workflows based on applicable requirements and source obligations.

India's DPDP Act, 2023 defines personal data broadly and regulates processing of digital personal data; its commencement has been phased by government notification. The implementation should therefore be designed for the Act and applicable rules as they come into force, with legal review before any production deployment. See the official Act and commencement notification in Appendix A.

---

## 14. Success Metrics

### Product metrics

- % of ingested observations normalized successfully.
- % with usable geolocation.
- Classification macro-F1 on a labeled validation set.
- Duplicate precision/recall.
- Incident clustering precision/recall.
- % of incidents with at least one independent corroborating source.
- Median observation-to-incident latency.
- Reviewer time per report.

### Competition demo metrics

Target, not guaranteed:

- 1,000+ simulated observations replayed successfully.
- <10 s end-to-end median processing latency under demo load.
- >90% exact duplicate elimination in controlled test set.
- Demonstrable separation of observations vs incidents.
- Complete end-to-end review workflow.

---

## 15. MVP Release Scope

### Must Have

- Citizen report submission.
- At least one permitted external connector.
- Weather API ingestion.
- Redpanda/Kafka-compatible stream.
- PostgreSQL/PostGIS.
- Event classifier.
- Location resolution.
- Deduplication.
- Incident clustering.
- Confidence/evidence breakdown.
- Live map.
- Filters.
- Admin verification.
- Audit log.
- Simulation mode.

### Should Have

- Media AI.
- Multilingual processing.
- Parquet data lake.
- Spark batch analytics.
- Alerting.
- Grafana observability.

### Could Have

- Satellite/radar overlays.
- More source connectors.
- Mobile PWA.
- Advanced anomaly detection.
- Forecast-vs-observation divergence analysis.

---

## 16. Product Risks

| Risk | Impact | Mitigation |
|---|---|---|
| External API restrictions/outage | High | Source abstraction + simulation mode + citizen channel |
| Social media licensing constraints | High | Use permitted APIs, store only what terms allow |
| False AI confidence | High | Explainable evidence + human verification |
| Geolocation errors | High | Provenance + confidence + manual correction |
| Duplicate incident inflation | High | Semantic + geo + time clustering |
| AI provider outage | Medium | Local model fallback for core classification |
| Media storage cost | Medium | Object storage + retention policy |
| Dashboard overload | Medium | Server-side aggregation + map clustering |
| Security breach | Critical | RBAC + least privilege + secrets management + audit |
| Legal/privacy non-compliance | Critical | Data minimization + legal review + source-specific policies |

---

## 17. Competition Demo Story

1. Citizen submits a flood report with photo.
2. Report appears in ingestion stream.
3. NLP extracts event and location.
4. Weather service supplies corroborating conditions.
5. Similar social/citizen observations arrive.
6. Deduplication groups them.
7. Incident engine creates one incident from multiple observations.
8. Confidence evidence panel updates.
9. Incident appears on India map without refresh.
10. Admin verifies it.
11. Dashboard analytics update.
12. Judge switches to historical/simulation view to demonstrate scale.

---

## 18. Roadmap

### Phase 0 — Foundation
Repository, Docker, CI, database, authentication.

### Phase 1 — End-to-end MVP
Citizen → stream → database → API → map.

### Phase 2 — Intelligence
Classification, geolocation, deduplication, clustering.

### Phase 3 — Verification
Weather correlation, media analysis, evidence engine, review queue.

### Phase 4 — Scale
Parquet, Spark, batch analytics, observability, connector expansion.

### Phase 5 — Production hardening
Security audit, legal/data governance review, SLOs, DR, load testing.

---

## 19. Acceptance Criteria — MVP

The MVP is complete when all of the following are true:

- A citizen report can be submitted with optional media.
- The report is persisted and published to the stream.
- A processor consumes it and produces normalized output.
- AI classifies the event.
- Location is resolved with provenance.
- Duplicate reports can be detected.
- Multiple related reports can form one incident.
- A confidence explanation is generated.
- The incident appears on the map.
- Filters update the data view correctly.
- A reviewer can verify/reject/unconfirm a report.
- Every privileged action is logged.
- Demo data can be replayed through the same production-like pipeline.
- The system continues operating if one external connector is disabled.

---

## Appendix A — Reference Governance Sources

1. Digital Personal Data Protection Act, 2023 — Ministry of Electronics and Information Technology, Government of India: https://www.meity.gov.in/static/uploads/2024/02/Digital-Personal-Data-Protection-Act-2023-1.pdf
2. DPDP Act commencement notification dated 13 November 2025 — Government of India Gazette: https://www.meity.gov.in/static/uploads/2025/11/c56ceae6c383460ca69577428d36828b.pdf
3. CERT-In Directions under Section 70B: https://www.cert-in.org.in/Directions70B.jsp
4. CERT-In secure application design/development guideline index: https://www.cert-in.org.in/s2cMainServlet?pageid=GUIDLNVIEW01
5. IMD official site: https://mausam.imd.gov.in/
6. X developer documentation: https://developer.x.com/

---
