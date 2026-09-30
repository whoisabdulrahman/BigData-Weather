# Bharat Weather Intelligence Platform (BWIP)
## National Weather Big Data Analytics Platform — Ministry of Earth Sciences (IMD)

A competition-grade disaster-management data platform for collecting, processing, correlating, verifying, clustering, and visualizing weather-related observations across India.

---

## 1. Core Architecture Invariant

> **Observation / Report ≠ Incident ≠ Fact**

* A social post, citizen report, or sensor ping is an **Observation**, not an incident.
* Multiple independent observations are normalized, geolocated, and clustered into **Incidents**.
* AI models produce probabilistic confidence scores and evidence signals, not absolute truth.
* Authorized human reviewers verify or reject incidents through an operational review workflow.

```text
DATA SOURCE → RAW OBSERVATION → NORMALIZATION → CLASSIFICATION → GEOLOCATION
    → DEDUPLICATION → CORROBORATION → INCIDENT CLUSTERING → INCIDENT → DASHBOARD / ANALYTICS
```

---

## 2. Monorepo Structure

```text
.
├── apps/
│   ├── api/                   # FastAPI backend (REST & WebSocket APIs, auth, routes)
│   └── web/                   # Next.js frontend (MapLibre map, operational dashboard, admin panel)
├── services/
│   ├── ingestion/             # Source connectors (Citizen, Weather API, Social, Datasets)
│   └── processing/            # Normalizer, deduplication, incident clustering, corroboration
├── infra/
│   └── docker-compose.yml     # PostgreSQL+PostGIS, Redpanda, Redis, MinIO
├── scripts/                   # Replay runners, synthetic data generators, database seeds
├── tests/                     # Automated unit and integration test suite
├── docs/                      # Architectural specifications and continuous implementation state
└── .agents/                   # Continuous multi-agent engineering rules and workflows
```

---

## 3. Quickstart & Local Setup

### Prerequisites
* Python 3.12+ (tested with Python 3.13)
* Node.js 18+ (tested with Node.js 22)
* Docker & Docker Compose

### Step 1: Environment Setup
```bash
cp .env.example .env
```

### Step 2: Infrastructure with Docker
```bash
docker compose -f infra/docker-compose.yml up -d
```
This starts:
* **PostgreSQL + PostGIS**: `localhost:5432`
* **Redpanda (Kafka)**: `localhost:9092` (Console: `http://localhost:8080`)
* **Redis**: `localhost:6379`
* **MinIO Object Store**: `localhost:9000` (Console: `http://localhost:9001`)

### Step 3: Run Backend API
```bash
# Install dependencies
py -m pip install -r apps/api/requirements.txt

# Start API service
py -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```
Swagger UI available at: `http://localhost:8000/docs`  
Health check: `http://localhost:8000/health`  
Readiness check: `http://localhost:8000/ready`

### Step 4: Run Tests
```bash
py -m pytest tests/ -v
```

---

## 4. Documentation & Continuity

* Product Requirements Document: [docs/01_PRD.md](docs/01_PRD.md)
* Technical Architecture: [docs/02_Technical_Architecture.md](docs/02_Technical_Architecture.md)
* Security & Access Governance: [docs/03_Security_Access_Governance.md](docs/03_Security_Access_Governance.md)
* Frontend Specification: [docs/04_Frontend_Specification.md](docs/04_Frontend_Specification.md)
* Feature Ticket Backlog: [docs/05_Feature_Ticket_List.md](docs/05_Feature_Ticket_List.md)
* Current Implementation State: [docs/IMPLEMENTATION_STATE.md](docs/IMPLEMENTATION_STATE.md)
* Decision Register: [docs/DECISIONS.md](docs/DECISIONS.md)
* Changelog: [docs/CHANGELOG.md](docs/CHANGELOG.md)
# BigData-Weather
