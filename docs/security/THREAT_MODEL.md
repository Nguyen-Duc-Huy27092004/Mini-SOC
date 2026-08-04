# STRIDE Threat Modeling Specification
## Enterprise Mini SOC Platform

### 1. STRIDE Threat Model Matrix

| STRIDE Category | Threat Description | Attack Vector | Impact | Mitigation Control |
| :--- | :--- | :--- | :--- | :--- |
| **Spoofing** | Adversary spoofs JWT token or impersonates an analyst. | Stolen JWT secret or weak signature validation. | High | RS256/HS256 strong signing, secret rotation, short 15-min TTL, Redis token revocation blacklisting. |
| **Tampering** | Malicious insider modifies alert audit logs or incident history. | Direct SQL execution or missing ORM mutation controls. | Critical | Append-only DB tables, DB user privilege restriction, cryptographic log hashing. |
| **Repudiation** | Analyst denies approving an unauthorized SOAR firewall block. | Missing or unauthenticated execution logs. | High | Mandatory approval gate recording user ID, IP address, timestamp, and signature in audit DB (BR-004). |
| **Information Disclosure** | External attacker sniffs security alerts containing internal host IPs. | Plaintext HTTP / WS transmission. | High | Strict HTTPS/WSS enforcement via Nginx SSL, HSTS header, secure cookies. |
| **Denial of Service** | Threat actor floods API with 10,000 EPS to crash backend. | High-volume ingestion spamming. | High | Rate limiting middleware (Redis sliding window), async log queues, connection pooling. |
| **Elevation of Privilege** | Tier 1 Analyst bypasses RBAC to approve SOAR actions. | Missing role checks in FastAPI endpoint handlers. | Critical | Centralized FastAPI `Depends(require_role(...))` dependency injection middleware. |
