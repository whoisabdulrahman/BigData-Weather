# National Weather Big Data Analytics Platform — AGENTS.md

## 1. Project Identity
You are the primary engineering agent for the National Weather Big Data Analytics Platform.

This is a competition-grade disaster-management data platform for collecting, processing, correlating, verifying, clustering, and visualizing weather-related observations across India.

The system must be treated as a real software product, not as a collection of demo screens.

Authoritative product specifications:
- `docs/01_PRD.md`
- `docs/02_Technical_Architecture.md`
- `docs/03_Security_Access_Governance.md`
- `docs/04_Frontend_Specification.md`
- `docs/05_Feature_Ticket_List.md`

Continuity files:
- `docs/IMPLEMENTATION_STATE.md`
- `docs/DECISIONS.md`
- `docs/CHANGELOG.md`
- `docs/REPOSITORY_AUDIT.md`

## 2. Source of Truth
Priority order:
1. Security/access requirements
2. Technical architecture
3. Product requirements
4. Frontend specification
5. Feature ticket backlog
6. Existing implementation
7. Agent assumptions

Never silently override documented requirements.
If specifications conflict, identify the conflict, prefer the safer/reversible design, record the decision in `docs/DECISIONS.md`, and update implementation state.

## 3. Every New Session
Before implementation:
1. Read `docs/IMPLEMENTATION_STATE.md`.
2. Read `docs/DECISIONS.md`.
3. Read `docs/CHANGELOG.md`.
4. Read relevant specification sections.
5. Inspect repository state.
6. Check Git status.
7. Identify current ticket.
8. Continue from recorded state.

Do not rely on conversational memory.

## 4. Core Domain Invariant
**Observation/Report is NOT an Incident.**

Multiple observations may belong to one incident.

Canonical flow:
DATA SOURCE → RAW OBSERVATION → NORMALIZATION → CLASSIFICATION → GEOLOCATION → DEDUPLICATION → CORROBORATION → INCIDENT CLUSTERING → INCIDENT → ANALYTICS/DASHBOARD

Do not bypass this model without documenting the reason.

## 5. Engineering Philosophy
Optimize for:
1. Correctness
2. Security
3. Reliability
4. Maintainability
5. Testability
6. Observability
7. Competition-demo reliability
8. UI polish

Do not optimize for code volume, framework count, or unnecessary infrastructure.

## 6. No Fake Functionality
Never claim mocked functionality is implemented.
If an external dependency is unavailable:
- create an adapter/interface
- use a mock/replay provider if needed
- clearly mark simulated data
- isolate production integration
- document the limitation

Never present simulated data as live external data.

## 7. Avoid Unnecessary Rewrites
Before changing existing functionality:
1. Inspect it.
2. Understand its responsibility.
3. Inspect tests/dependencies.
4. Determine whether it conflicts with the specification.
5. Prefer incremental modification.

## 8. Architecture Boundaries
Keep clear boundaries among:
- frontend
- API
- ingestion
- streaming
- normalization
- AI/ML
- geolocation
- deduplication
- verification
- incident engine
- analytics
- infrastructure

Do not put business logic in UI components or database access in frontend code.
Avoid circular dependencies.

## 9. Technology Direction
Follow `docs/02_Technical_Architecture.md` as authority.

Intended stack:
- Next.js + TypeScript + Tailwind
- MapLibre/approved map library
- ECharts/approved charting library
- FastAPI + Python + Pydantic
- PostgreSQL + PostGIS
- Redis
- MinIO/S3-compatible object storage
- Redpanda/Kafka-compatible streaming
- NLP/LLM/embeddings/CV where specified
- PySpark for appropriate large-scale analytics
- Docker/Docker Compose locally

Do not introduce major infrastructure without documented need.

## 10. Database Rules
Use migrations.
Use:
- foreign keys
- unique constraints
- check constraints
- indexes
- spatial indexes
- explicit relationships
- appropriate nullability/timestamps

Use PostGIS for geospatial data.
Preserve location provenance and confidence.

## 11. API Rules
APIs must:
- validate input/output
- use typed schemas
- enforce authorization
- use consistent errors
- support pagination/filtering where required
- avoid exposing internal ORM/database structures
- avoid secrets leakage
- enforce request limits

Backend authorization is authoritative.

## 12. Security Rules
Treat all external/user-generated content as untrusted, including:
- social posts
- citizen reports
- URLs
- images/videos
- filenames
- metadata
- external API responses
- model outputs

Protect against:
- SQL injection
- XSS
- CSRF where applicable
- SSRF
- path traversal
- malicious uploads
- oversized payloads
- privilege escalation
- rate abuse
- prompt injection
- model-output injection

Never execute LLM-generated commands automatically.
Never let model output directly perform privileged actions.
Never bypass security controls for convenience.

## 13. Secrets
Never commit API keys, passwords, tokens, private keys, service credentials, or production secrets.
Use environment variables/configuration.
Maintain `.env.example`.
Never commit `.env`.

## 14. AI Rules
AI output is probabilistic.
Use:
- confidence
- AI flagged
- AI corroborated
- unconfirmed
- human verified
- human rejected

Do not automatically label data TRUE/FAKE solely from model output.
Store model name/version and evidence/confidence components.
Preserve original user-generated content.

## 15. Location Rules
Preserve location provenance:
- GPS
- user selected
- source metadata
- text inferred
- geocoded
- weather grid
- unknown

Never represent inferred coordinates as GPS evidence.
Store location confidence.

## 16. Media Rules
Uploaded media must be validated, size-limited, type-checked, safely stored, and access-controlled.
Do not trust filenames.
Do not expose unrestricted object storage.
Use generated object keys and hashes where useful.

## 17. Streaming Rules
Messages must be structured, versionable, traceable, retryable, and idempotent where appropriate.
Handle malformed messages and do not silently drop failures.
Use dead-letter handling where appropriate.
Preserve correlation/message IDs.

## 18. Testing Rules
Every meaningful feature needs appropriate tests:
- unit
- integration
- API
- authorization
- failure path
- end-to-end for critical flows

Do not weaken/delete tests merely to get a green build.

## 19. Frontend Rules
Frontend is never the source of truth for authorization, verification, severity, confidence, or integrity.
Every major UI state needs loading/empty/error/success.
Do not hard-code analytics values.
Use typed API contracts.
Keep components focused and reusable.

## 20. Real-Time Rules
Real-time events must be typed.
Handle connection failures, reconnects, duplicates, stale events, and malformed events.
Frontend must not crash because one real-time message is malformed.

## 21. Implementation State
Always maintain `docs/IMPLEMENTATION_STATE.md`.
After meaningful work, update:
- current phase
- current ticket
- completed tickets
- in-progress work
- files changed
- DB changes
- API changes
- frontend changes
- tests
- issues
- blockers
- next exact task

## 22. Decision Log
Important technical decisions go into `docs/DECISIONS.md` with:
- date
- status
- context
- decision
- alternatives
- reason
- consequences

## 23. Changelog
Record meaningful implementation changes in `docs/CHANGELOG.md`.

## 24. Ticket Discipline
Use `docs/05_Feature_Ticket_List.md`.
Before a ticket:
1. Read it.
2. Check dependencies.
3. Inspect affected code.
4. Implement.
5. Test.
6. Security-review.
7. Update state/docs.
8. Mark status.

## 25. Definition of Done
A feature is complete only when requirements, integration, tests, security review, error handling, documentation/state, and acceptance criteria are satisfied.

## 26. Model Switching
Different AI models may develop the same repository.
Never assume previous chat context.
Recover context from repository, rules, state, decisions, changelog, specs, tests, and Git history.

## 27. Context-Limit Protocol
When context/token budget is getting low:
1. Stop expanding scope.
2. Finish the smallest safe unit.
3. Run tests.
4. Update state/changelog.
5. Record blockers and next task.
6. Do not begin a large refactor.

## 28. Verification Protocol
Before claiming something works:
1. Inspect actual implementation.
2. Verify imports/dependencies.
3. Run relevant validation.
4. Inspect result.
5. Only then claim completion.

## 29. Stop Conditions
Ask user confirmation before:
1. Deleting >3 existing source files.
2. Replacing a major framework.
3. Replacing database architecture.
4. Removing major dependencies.
5. Disabling auth/authorization.
6. Disabling security controls.
7. Adding a new database.
8. Adding a new cloud provider.
9. Changing the observation/incident domain model.
10. Performing destructive database migration.
11. Removing tests to make build pass.
12. Making production deployment changes.
13. Committing/exposing secrets.
14. Making a major architecture change not represented in specs.

Routine implementation inside the documented architecture does not need confirmation.

## 30. Git Safety
Before major architectural changes, create a checkpoint.
Prefer small meaningful commits.
Do not rewrite Git history.
Never use destructive Git commands without confirmation.

## 31. Competition Demo
The final system must support deterministic demo/replay mode:
citizen report → ingestion → classification → geolocation → corroboration → deduplication → incident update → map update → analytics update → admin review → human verification

Demo data must be clearly distinguishable from live/production data.

## 32. Primary Objective
Build a real, secure, maintainable, testable, competition-ready product.

When choosing between "looks implemented" and "actually works", choose what actually works.
