# Changelog

All meaningful implementation changes are recorded here.

## [0.3.0] - 2026-09-30

### Added
- **Live infrastructure verification (Steps 1-4):** all five Docker services healthy; Redpanda cluster healthy; `redis` PING/SET/GET/DEL verified; MinIO buckets `weather-media` and `weather-raw-payloads` created and exercised with PUT/GET/DELETE.
- `alembic/versions/002_reconcile_postgis_schema.py`: idempotent reconciliation of the live schema with the SQLAlchemy models — `report_hash`, `processing_status`, `metadata_json`, `geography(Point,4326)` conversion, `bwip_sync_location_column()` trigger, GiST indexes and FK checks. `001_initial_schema` now no-ops when the schema already exists, and its `downgrade()` requires `ALLOW_DESTRUCTIVE_DOWNGRADE=1`.
- `STREAM_MODE` setting (`redpanda` = mandatory live broker, `bus` = in-memory test/demo transport) plus `KAFKA_CONSUMER_GROUP`, `KAFKA_TOPIC_BOOTSTRAP`, `KAFKA_AUTO_OFFSET_RESET`.
- `EventProducer.ensure_topics()` bootstraps `weather.raw.v1` and `weather.dlq.v1` through the aiokafka admin client; `StreamPublishError` is the hard-failure signal for an unreachable broker.
- Live consumer loop with manual offset commits, bounded retries with backoff, structured dead-letter routing, and an outer reconnect loop so an infrastructure failure never silently kills the worker.
- `services/streaming/worker.py` (`python -m services.streaming.worker`) as the production consumer entrypoint.
- `apps/api/core/health.py`: real readiness probes for PostgreSQL/PostGIS, Redis, Redpanda and MinIO (previously hard-coded `healthy`), plus idempotent `ensure_object_store_buckets()` invoked from the API lifespan.
- `scripts/seed_demo_incidents.py`: idempotent deterministic demo data, tagged `metadata_json.demo = true`.
- Live test suites: `tests/test_live_pipeline_e2e.py` (full pipeline, malformed→DLQ, duplicate delivery) and `tests/test_failure_paths.py` (dead broker→503, dead database→retry+DLQ), with `tests/live_utils.py` helpers and `tests/conftest.py`.
- Frontend tooling: `typecheck` npm script, `.eslintrc.json` (`next/core-web-vitals`), dev dependencies `eslint` and `eslint-config-next`.

### Changed
- `POST /api/v1/citizen/reports` returns HTTP 503 with an explicit `NOT accepted` detail when the broker is unreachable, and reports the `transport` actually used.
- `GET /api/v1/incidents` and `GET /api/v1/analytics/summary` are now backed by PostgreSQL aggregates; the hard-coded `DEMO_INCIDENTS` and KPI numbers were removed.
- Pipeline validates the nested canonical envelope and treats `IntegrityError` on insert as a duplicate (concurrent delivery) instead of failing the message.
- Pipeline `POST`/`GET` schemas and lifespan updated for the real producer lifecycle and object-store bootstrap.

### Fixed
- `AIOKafkaProducer.__init__() got an unexpected keyword argument 'max_retries'` — every live connection failed at construction; removed the unsupported kwarg and moved topic bootstrap out of the fatal path.
- Consumer no longer exits permanently when a DLQ publish or database outage occurs (bounded reconnect with backoff, uncommitted offsets are redelivered).

### Verified
- `$env:PYTHONPATH="."; py -m pytest tests/ -v` → **20 passed, 0 failed in 33.69s** against live Docker services.
- E2E boundary crossing confirmed: `POST /api/v1/citizen/reports` → `weather.raw.v1` → consumer → `reports`/`incidents`/`incident_reports` in PostGIS → `GET /api/v1/incidents/{id}` → analytics summary; 3 observations collapse into 1 incident (`observation_count = 3`).
- Idempotent re-delivery persists exactly one observation; malformed messages reach `weather.dlq.v1` and are never persisted.
- Live `/ready` returns `status: ready` with database, cache, streaming and object_store all `healthy`.
- Frontend: `npx tsc --noEmit` clean, `npm run lint` clean, `npm run build` success, `npm run start` serving `GET /` → 200.

---

## [0.2.0] - 2026-09-30

### Added
- Alembic database migration framework configured (`alembic/`, `alembic/env.py`, `alembic/versions/001_initial_schema.py`). Dynamically loads `DATABASE_URL` from Pydantic settings and imports all domain models.
- SQLAlchemy domain models: `Report`, `Incident`, `IncidentReport`, `VerificationResult`, `AuditLog` in `apps/api/models/`.
- `ObservationPipelineEngine` (`services/processing/pipeline.py`): full canonical observation processing with validation, idempotency hash check, DB persistence, geo-temporal incident clustering, and new incident spawning.
- `StreamEventBus` (`services/streaming/bus.py`): deterministic in-memory publish/subscribe bus used as local dev fallback when Redpanda broker is unavailable (documented in DEC-002).
- `EventProducer` (`services/streaming/producer.py`): attempts live Redpanda publish, falls back to `StreamEventBus`.
- `EventConsumer` (`services/streaming/consumer.py`): polls `StreamEventBus`, processes each event through the pipeline engine, routes malformed events to a dead-letter queue.
- `compute_report_hash` (`services/processing/idempotency.py`): deterministic SHA-256 fingerprint over source, text, timestamp, coordinates, and event type.
- `haversine_distance_meters` (`services/processing/clustering.py`): pure-Python WGS-84 haversine distance used for spatial clustering.
- Vertical slice integration test suite (`tests/test_vertical_slice_pipeline.py`, 8 requirements): publish, consumer persistence, incident create, incident update, idempotency suppression, DLQ routing.

### Fixed
- `TypeError: can't subtract offset-naive and offset-aware datetimes` in pipeline `time_diff` and `max()` comparisons — added `ensure_utc()` helper ensuring all datetime comparisons are timezone-aware.
- `apps/api/main.py` updated to use `lifespan` async context manager instead of deprecated `on_event`.
- Updated `apps/api/requirements.txt` to include `alembic`, `geoalchemy2`, `aiokafka`.

### Verified
- Executed full test suite (`$env:PYTHONPATH="."; py -m pytest tests/ -v`): **15 passed, 0 failed** in 1.31s.
- Citizen report pipeline: `POST /api/v1/citizen/reports` → event publish → consumer → pipeline engine → SQLite DB → incident creation.
- Observation != Incident invariant: a second nearby observation correctly associates with an existing incident rather than spawning a duplicate.
- Idempotency: identical report hash suppressed at pipeline boundary.
- DLQ: malformed events routed to dead-letter queue without crashing the consumer.

### Documentation
- `docs/IMPLEMENTATION_STATE.md`: Strict verification pass performed. Docker infrastructure downgraded from `VERIFIED` to `IMPLEMENTED` (Docker daemon was not running during this session). All items now reflect actual tested state.

---

## [0.1.0] - 2026-09-29

### Added
- Completed initial repository audit (`docs/REPOSITORY_AUDIT.md`).
- Monorepo directory structure: `apps/api`, `apps/web`, `services/ingestion`, `services/processing`, `infra`, `tests`.
- Root environment configuration template (`.env.example`) and comprehensive `.gitignore`.
- Root `README.md` with architectural invariants, quickstart guides, and service layout.
- Docker Compose infrastructure (`infra/docker-compose.yml`) for PostgreSQL+PostGIS, Redpanda, Redis, and MinIO with container health checks and persistent volumes.
- Database initialization script (`infra/init-db.sql`) with PostGIS spatial extensions, reports, incidents, incident_reports, verification_results, audit_logs tables and GiST spatial indexes.
- FastAPI backend application (`apps/api`) with typed Pydantic v2 schemas, settings management, structured logging, CORS, and security headers middleware.
- Liveness (`/health`) and Readiness (`/ready`) API probes.
- Citizen reporting API (`POST /api/v1/citizen/reports`) enforcing India bounding-box coordinates (6°N–38°N, 68°E–98°E).
- Clustered incident query API (`GET /api/v1/incidents`, `GET /api/v1/incidents/{id}`) with multi-attribute filtering.
- Analytics summary API (`GET /api/v1/analytics/summary`).
- Ingestion connector contract (`services/ingestion/base.py`).
- Incident clustering engine (`services/processing/clustering.py`) implementing haversine geo-temporal grouping while preserving the `Observation != Incident` invariant.
- Next.js 14 frontend application shell (`apps/web`) with dark mode tokens, glassmorphism UI, KPI cards, interactive national map surface, incident detail feed, and citizen report submission modal.
- Automated test suite (`tests/`) covering health probes, security headers, spatial clustering engine, and citizen reporting validation.

### Changed
- Transitioned repository state from `PHASE_0_REPOSITORY_FOUNDATION` unstarted to active working baseline.

### Verified
- Executed full test suite (`pytest tests/ -v`): 10 passed in 0.62s.
- Validated API execution via TestClient for health probes and incidents queries.
