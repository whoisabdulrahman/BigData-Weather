---
trigger: always_on
description: "Testing, verification and definition-of-done rules"
---

# Testing Rules

Code generation is not feature completion.

Before marking a ticket complete:
1. Run relevant unit tests.
2. Run relevant integration tests.
3. Run type checking.
4. Run linting.
5. Verify migrations where applicable.
6. Verify critical user flows.
7. Review error paths.
8. Review authorization/security implications.

Do not delete or weaken tests to get a green build.

Before claiming a feature works, actually execute the relevant validation.

For critical pipeline changes, test:
input → ingestion → processing → persistence → API → frontend

Document known failures in:
`docs/IMPLEMENTATION_STATE.md`
