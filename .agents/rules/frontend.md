---
trigger: glob
globs: ["apps/web/**", "frontend/**", "**/*.tsx", "**/*.ts"]
description: "Frontend engineering and UX rules"
---

# Frontend Rules

Follow:
@docs/04_Frontend_Specification.md
@docs/01_PRD.md

The frontend is not the source of truth for authorization, verification, severity, confidence, or data integrity.
All protected actions must be backend-authorized.

Every major view needs:
- loading
- empty
- error
- success

Do not hard-code analytics values.
Use typed API contracts.
Keep components focused and reusable.
Do not put domain/business logic into presentation components when it belongs elsewhere.

For maps:
- use clustering
- avoid huge DOM marker counts
- handle missing coordinates gracefully

For real-time:
- validate incoming events
- handle reconnects
- ignore malformed events safely
- prevent duplicate application
