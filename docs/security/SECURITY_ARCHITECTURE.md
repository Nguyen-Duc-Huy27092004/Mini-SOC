# Zero-Trust Security Architecture Blueprint
## Enterprise Mini SOC Platform

### 1. Zero-Trust Security Principles
The **Enterprise Mini SOC Platform** implements a strict **Zero-Trust Architecture (ZTA)** based on NIST SP 800-207 principles:
1. **Never Trust, Always Verify:** Every incoming HTTP and WebSocket request MUST authenticate via signed JSON Web Tokens (JWT) and be evaluated against strict RBAC rules regardless of network origin.
2. **Least Privilege Access:** Users, background tasks, and API tokens possess only the minimal set of permissions required for their role (`Admin`, `SOC_Manager`, `SOC_Analyst_T2`, `SOC_Analyst_T1`, `Read_Only`).
3. **Assume Breach & Defense-in-Depth:** Every layer (Nginx TLS, FastAPI Pydantic validation, Redis isolation, PostgreSQL encrypted connections) is hardened independently.

---

### 2. Authentication & Session Security Framework
- **JWT Architecture:** Short-lived RSA256/HS256 access tokens (15-minute expiration) paired with refresh tokens (7-day expiration with sliding renewal and revocation list in Redis).
- **Password Policy:** Minimum 12 characters, requiring uppercase, lowercase, numbers, and special symbols; hashed via `argon2id` or `bcrypt` with work factor 12+.
- **Account Lockout:** Maximum 5 failed login attempts per 15 minutes triggers automatic IP/User temporary lock.

---

### 3. Role-Based Access Control (RBAC) Permission Matrix

| Role | Read Alerts / Metrics | Assign & Triage Incidents | Trigger SOAR Playbooks | Approve Destructive Actions (BR-001) | Manage System & Users |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Admin** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **SOC_Manager** | ✅ | ✅ | ✅ | ✅ | ❌ |
| **SOC_Analyst_T2** | ✅ | ✅ | ✅ | ❌ (Request Only) | ❌ |
| **SOC_Analyst_T1** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Read_Only** | ✅ | ❌ | ❌ | ❌ | ❌ |

---

### 4. Data Security & Encryption Baseline
- **Encryption in Transit:** TLS 1.3 mandatory across Nginx, backend REST APIs, WebSocket channels (`wss://`), and database connections.
- **Encryption at Rest:** Sensitive database fields (API Keys, external service tokens, DB credentials) encrypted using AES-256-GCM.
- **Secrets Management:** Injected exclusively via system environment variables / `.env` files. Hardcoded keys in source code are blocked by pre-commit hooks and CI security checks.
