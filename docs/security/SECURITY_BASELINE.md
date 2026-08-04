# Security Controls Baseline & Hardening Specification
## Enterprise Mini SOC Platform

### 1. OWASP API Security Top 10 Mitigation Baseline

- **API1:2023 Broken Object Level Authorization (BOLA):** Explicit ID authorization verification in Python FastAPI router dependencies before returning DB records.
- **API2:2023 Broken Authentication:** Secure OAuth2 scheme with Bearer JWT tokens, automatic lockout after 5 invalid attempts, and strict token expiration.
- **API3:2023 Broken Object Property Level Authorization:** Strict Pydantic V2 response schemas preventing mass assignment and sensitive field leakage.
- **API4:2023 Unrestricted Resource Consumption:** Redis-backed rate limiting per IP and per authenticated user.
- **API5:2023 Broken Function Level Authorization:** RBAC permission decorator enforcing role hierarchy across all endpoint routes.
- **API8:2023 Security Misconfiguration:** Hardened Nginx configuration (HSTS, Content-Security-Policy, X-Frame-Options: DENY, X-Content-Type-Options: nosniff).

---

### 2. Container & OS Hardening Guidelines
1. **Non-Root Execution:** All Docker containers MUST execute using dedicated non-root service users (`appuser`, `uid:10001`).
2. **Minimal Base Images:** Use official lightweight Alpine or Debian-slim base images (`python:3.12-slim`, `node:20-alpine`).
3. **Read-Only Root Filesystem:** Enable read-only container filesystems with dedicated tmpfs mounts for temporary files.
4. **No Environment Secrets Hardcoding:** Secrets loaded exclusively via environment variables or secret volumes.
