---
trigger: always_on
description: "Security, privacy and access-control rules"
---

# Security Rules

Follow:
@docs/03_Security_Access_Governance.md

Treat all external and user-generated data as untrusted.

Protect against:
- SQL injection
- XSS
- CSRF where applicable
- SSRF
- path traversal
- malicious uploads
- oversized requests
- privilege escalation
- rate abuse
- prompt injection
- model-output injection

Never:
- hard-code secrets
- commit credentials
- expose private citizen data publicly
- trust frontend authorization
- execute LLM-generated commands
- let model output directly perform privileged actions
- expose unrestricted object storage

Use environment variables/configuration for secrets.
Require server-side authorization for protected operations.
Maintain audit logs for security-sensitive admin actions.

Before adding external dependencies, assess data sent, credentials, trust boundary, failure behavior, and privacy impact.
