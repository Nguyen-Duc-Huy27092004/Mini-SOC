# Epic Definitions & Structure
## Enterprise Mini SOC Platform

### 1. Epic Overview Matrix

| Epic ID | Epic Name | Business Value | Owner | Priority | Dependencies |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **EP-001** | Real-Time Monitoring & Detection | Live threat visibility, alert stream ingestion, Zabbix integration | PO / Solution Architect | Must Have (MVP) | None |
| **EP-002** | Threat Intelligence & Enrichment | Automated IOC extraction, GeoIP mapping, VirusTotal/AbuseIPDB score | PO / Threat Intel Eng | Must Have (MVP) | EP-001 |
| **EP-003** | Incident & SLA Management | Ticket workflow, analyst assignment, SLA countdown, PIR export | PO / SOC Lead | Must Have (MVP) | EP-001 |
| **EP-004** | SOAR Playbooks & Response | Automated firewall IP blocking, host isolation with human approval | PO / SOAR Eng | Must Have (MVP) | EP-002, EP-003 |
| **EP-005** | AI Security Assistant | Natural language alert summary, root cause hypothesis, risk score | PO / AI Security Eng | Should Have | EP-002, EP-003 |
| **EP-006** | Platform Security & Governance | JWT Auth, RBAC enforcement, immutable audit logging, rate limit | PO / Sec Architect | Must Have (MVP) | None |

---

### 2. Detailed Epic Specifications

#### EP-001: Real-Time Monitoring & Detection
- **Business Value:** Provides immediate operational awareness across security events (Wazuh) and system infrastructure health (Zabbix). Reduces MTTD (Mean Time to Detect) to under 1 minute.
- **Success Criteria:** 100% of incoming Wazuh events ingested within 500ms; continuous WebSocket streaming to frontend; zero dropped alerts under 1,000 EPS.

#### EP-002: Threat Intelligence & Enrichment
- **Business Value:** Automatically enriches incoming alerts with external threat reputation and geographic location, eliminating manual copy-pasting of IP addresses into VirusTotal.
- **Success Criteria:** 98%+ of external IP indicators enriched within 2 seconds; TI reputation cache hit rate > 80%.

#### EP-004: SOAR Playbooks & Automated Response
- **Business Value:** Empowers analysts to execute automated response actions (Firewall blocking, host isolation) in seconds while enforcing human approval gates to prevent business disruption.
- **Success Criteria:** Automated firewall IP block executed within 3 seconds of manager approval; 100% audit compliance for executed playbooks.
