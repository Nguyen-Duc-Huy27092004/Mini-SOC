# Assumptions, Constraints & Open Questions
## Enterprise Mini SOC Platform

### 1. Documented Assumptions

- **ASM-001:** The underlying deployment environment will have a running instance of Wazuh 4.x with accessible Manager API credentials and readable alert files (`alerts.json`).
- **ASM-002:** External network connectivity is available for Threat Intel API queries (VirusTotal, AbuseIPDB, AlienVault OTX) or mock fallbacks are allowed during offline development.
- **ASM-003:** An SMTP server or notification webhook (Slack/Discord/Teams) will be available for SOAR alert notifications.

---

### 2. Explicit System Constraints

- **CST-001 (Zero Autonomous Blocking):** Per Business Rule BR-001, AI and SOAR engines must not trigger destructive network isolation or account lockout without human approval.
- **CST-002 (Tech Stack Rigidity):** Backend MUST strictly use Python FastAPI, SQLAlchemy, Pydantic V2, PostgreSQL, Redis, and Alembic. Frontend MUST use React 18, TypeScript, Vite, Tailwind CSS, and Shadcn UI.
- **CST-003 (Resource Efficiency):** Total container stack footprint must run comfortably on standard SME infrastructure (4 CPU cores, 8GB RAM).

---

### 3. Open Questions for Product Owner & Architecture Handoff

> [!NOTE]
> **Q1 (Threat Intel API Rate Limits):** Should the platform support local GeoIP databases (MaxMind MMDB) to eliminate external network calls for geographic mapping? *(Proposed: Yes, bundle GeoLite2 City database locally).*

> [!NOTE]
> **Q2 (Audit Data Retention):** Should audit logs be archived to compressed local S3/MinIO compatible storage after 90 days? *(Proposed: Retain active DB partition for 90 days, export cold JSON compressed logs).*

---

### 4. Business Analyst Sign-Off & Handoff Checklist

- [x] Business Goal Defined
- [x] Stakeholders Identified
- [x] Functional & Non-Functional Requirements Documented
- [x] User Stories & Gherkin Acceptance Criteria Written
- [x] Use Cases & Workflows Defined
- [x] Business Rules Enforced (BR-001 to BR-005)
- [x] Risk Matrix & Quality Checklist Validated
- [x] Handoff Package complete under `docs/business/`

**Handoff Destination:** 02 Product Owner Agent & 03 Solution Architect Agent.
