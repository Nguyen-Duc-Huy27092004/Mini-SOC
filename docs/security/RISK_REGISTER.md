# Risk Register & Mitigations
## Enterprise Mini SOC Platform

### 1. Risk Register

| Risk ID | Threat Scenario | Score | Mitigation Standard | Residual Risk | Status |
| :--- | :--- | :---: | :--- | :---: | :--- |
| **SEC-R01** | OWASP API #1: Broken Object Level Authorization (BOLA) | **20 (High)** | Enforce tenant/incident ownership checks on `/api/v1/incidents/{id}` | Low | Mitigated |
| **SEC-R02** | OWASP API #2: Broken Authentication | **16 (High)** | JWT access token short TTL (15m) + Argon2id password hashing | Low | Mitigated |
| **SEC-R03** | OWASP API #4: Unrestricted Resource Consumption | **15 (High)** | Rate limiting middleware (100 req/min default, 1000 for ingestion) | Low | Mitigated |
| **SEC-R04** | Unauthorized Destructive SOAR Action | **25 (Critical)**| Mandatory Human Approval Gate (BR-001) enforced at API layer | Low | Mitigated |
