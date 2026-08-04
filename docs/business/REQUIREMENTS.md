# Requirements Traceability Matrix & Specifications
## Enterprise Mini SOC Platform

### 1. Functional Requirements Matrix (FR-001 to FR-025)

| Requirement ID | Module | Title | Priority (MoSCoW) | Dependencies | Traceability (User Story) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FR-001** | Ingestion | Real-time Wazuh Log Stream Processing | Must Have | Docker, Wazuh API | US-001 |
| **FR-002** | Ingestion | Alert Deduplication (60s sliding window) | Must Have | Redis Cache | US-001 |
| **FR-003** | Ingestion | Zabbix System Metric Sync | Should Have | Zabbix API | US-006 |
| **FR-004** | Threat Intel | Automated IOC Extraction (IP, Hash, Domain) | Must Have | FR-001 | US-002 |
| **FR-005** | Threat Intel | VirusTotal & AbuseIPDB Reputation Query | Must Have | Redis Cache | US-002 |
| **FR-006** | Threat Intel | GeoIP Database Lookup & ASN Mapping | Must Have | MaxMind GeoIP | US-002 |
| **FR-007** | AI Security | Natural Language Alert Summarization | Should Have | OpenAI/Ollama API | US-003 |
| **FR-008** | AI Security | Automated Incident Correlation & Root Cause | Should Have | FR-007 | US-003 |
| **FR-009** | AI Security | Dynamic Risk Score Calculation (0-100) | Must Have | FR-005, FR-008 | US-003 |
| **FR-010** | SOAR | Playbook Execution Framework | Must Have | PostgreSQL | US-004 |
| **FR-011** | SOAR | Firewall IP Block Action Handler | Must Have | FR-010 | US-004 |
| **FR-012** | SOAR | Human-in-the-Loop Approval Gate | Must Have | RBAC, Notification | US-004 |
| **FR-013** | Incident | Incident Ticket Lifecycle Management | Must Have | PostgreSQL | US-005 |
| **FR-014** | Incident | SLA Countdown & Visual Alerts | Must Have | WebSocket | US-005 |
| **FR-015** | Incident | Post-Incident Review (PIR) PDF Generator | Could Have | FR-013 | US-005 |
| **FR-016** | Asset | Asset Inventory & Criticality Mapping | Must Have | PostgreSQL | US-007 |
| **FR-017** | Security | JWT Auth with Access & Refresh Tokens | Must Have | FastAPI Auth | Security Rule |
| **FR-018** | Security | Role-Based Access Control (RBAC Enforcement) | Must Have | FR-017 | Security Rule |
| **FR-019** | Security | Immutable Audit Logging | Must Have | PostgreSQL | Security Rule |
| **FR-020** | UI/UX | Real-time Live Dashboard with WebSocket Stream | Must Have | React + Tailwind | US-001 |

---

### 2. Quality Checklist (INVEST Alignment)
- [x] **Independent:** All requirements can be implemented and tested independently.
- [x] **Negotiable:** Implementation details are flexible for Solution Architect optimization.
- [x] **Valuable:** Each story delivers clear business value to SOC operations.
- [x] **Estimable:** Requirements are concrete with specified technical boundaries.
- [x] **Small:** Designed for clean multi-agent architectural decomposition.
- [x] **Testable:** Accompanied by explicit Gherkin acceptance criteria.
