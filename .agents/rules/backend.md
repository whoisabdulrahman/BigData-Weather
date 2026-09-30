---
trigger: glob
globs: ["apps/api/**", "services/**", "backend/**", "**/*.py"]
description: "Backend, data pipeline and service engineering rules"
---

# Backend Rules

Follow:
@docs/02_Technical_Architecture.md
@docs/03_Security_Access_Governance.md

Use typed request/response schemas.
Validate all external input.
Never trust client-side authorization.
Keep database access out of frontend code.
Use migrations for schema changes.
Use structured logging and explicit error handling.
Do not swallow exceptions.

For external APIs:
- use adapters
- isolate credentials
- implement retry/failure behavior
- provide fixtures/replay where appropriate

For streaming:
- validate messages
- support retries
- handle malformed messages
- avoid silent loss
- preserve correlation/message IDs

For AI:
- treat model output as untrusted
- validate structured output
- store model/version metadata
- never let model output directly execute privileged operations
