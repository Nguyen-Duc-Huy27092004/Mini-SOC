# Feature Specifications
## Enterprise Mini SOC Platform

### 1. Feature Breakdown Matrix

| Feature ID | Epic | Feature Name | Priority | Story Points | Business Impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FT-001** | EP-001 | Wazuh WebSocket & JSON Alert Ingestion Engine | Must Have | 8 | Core security log stream ingestion |
| **FT-002** | EP-001 | Zabbix Infrastructure Health API Poller | Should Have | 5 | Server health & uptime monitoring |
| **FT-003** | EP-002 | Threat Intel Multi-Provider Aggregator (VT/AbuseIPDB/OTX) | Must Have | 8 | IOC automated reputation scoring |
| **FT-004** | EP-002 | GeoIP & ASN Metadata Enricher | Must Have | 3 | Geographical attack origin mapping |
| **FT-005** | EP-003 | Incident Ticket Management Board (Kanban & Table) | Must Have | 5 | Incident lifecycle workflow |
| **FT-006** | EP-003 | Real-time SLA Countdown & Escalation Engine | Must Have | 3 | Response SLA compliance |
| **FT-007** | EP-004 | Firewall IP Block Playbook with Approval Gate | Must Have | 8 | Automated threat containment |
| **FT-008** | EP-004 | Wazuh Active Response Host Isolation Playbook | Should Have | 5 | Compromised host isolation |
| **FT-009** | EP-005 | AI Natural Language Alert Summarizer & Root Cause | Should Have | 8 | Triage acceleration for analysts |
| **FT-010** | EP-006 | OAuth2/JWT Authentication & Role-Based Access Control | Must Have | 5 | Platform security foundation |
| **FT-011** | EP-006 | Centralized Immutable Audit Logging Framework | Must Have | 3 | Compliance & forensic non-repudiation |

---

### 2. Feature Acceptance Criteria

#### FT-007: Firewall IP Block Playbook with Approval Gate
- **Description:** Enables analysts to initiate an IP block on external firewalls. Requires approval from SOC Manager before executing the firewall rule API call.
- **Acceptance Criteria:**
  - **Given** an analyst clicks "Block IP" for IP `198.51.100.42`,
  - **When** the request is submitted, a pending approval record is logged with state `PENDING_APPROVAL`.
  - **Then** a real-time notification alerts the SOC Manager.
  - **When** SOC Manager approves, the system calls Firewall API, verifies execution, logs audit entry, and sets state to `EXECUTED`.
