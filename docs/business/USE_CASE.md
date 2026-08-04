# Detailed Use Cases
## Enterprise Mini SOC Platform

### 1. Use Case Matrix

| Use Case ID | Use Case Name | Primary Actor | Trigger |
| :--- | :--- | :--- | :--- |
| **UC-001** | Ingest & Enrich Security Alert | System (Wazuh Ingestor) | Inbound alert stream from Wazuh |
| **UC-002** | Perform AI Incident Investigation | SOC Analyst (Tier 2/3) | User clicks "Investigate with AI" |
| **UC-003** | Execute SOAR IP Block Playbook | SOC Analyst & Manager | Manual or Automated Playbook trigger |
| **UC-004** | Monitor System Health (Zabbix) | System / DevOps | High CPU/Disk usage alert from Zabbix |
| **UC-005** | Generate Incident Post-Incident Review (PIR) | Incident Responder | Incident transitions to `RESOLVED` |

---

### 2. Use Case Specifications

#### UC-001: Ingest & Enrich Security Alert
- **Primary Actor:** System (Wazuh Collector Engine)
- **Preconditions:** Wazuh API / log file stream is operational and backend ingestion service is healthy.
- **Main Success Scenario:**
  1. Wazuh triggers a security alert (e.g. Rule 100200 - Web Application Attack).
  2. Collector Engine receives alert JSON via queue.
  3. Deduplication filter checks if an identical alert from the same IP occurred in the last 60 seconds.
  4. System extracts IOCs (IP: `198.51.100.42`, Target Path: `/admin/login`).
  5. Threat Intel module executes GeoIP mapping and Redis lookup for VirusTotal/AbuseIPDB reputation.
  6. Mapped MITRE ATT&CK technique (e.g., `T1190 - Exploit Public-Facing Application`) is assigned.
  7. Alert is saved to PostgreSQL database.
  8. Alert is broadcast to all active WebSocket connected Analyst clients.
- **Extensions / Exception Flow:**
  - *5a. Threat Intel API rate limit reached:* System uses cached GeoIP data and marks TI score as `UNCERTAIN (Cached)`, continuing pipeline without failure.

#### UC-003: Execute SOAR IP Block Playbook
- **Primary Actor:** SOC Analyst (Tier 1/2), SOC Manager
- **Preconditions:** An active incident exists with identified malicious source IP `198.51.100.42`.
- **Main Success Scenario:**
  1. SOC Analyst selects incident `#INC-2026-0842` and clicks "Run Playbook: Block IP on Firewall".
  2. SOAR engine validates parameters and creates an Approval Gate ticket `#APPR-0104`.
  3. SOC Manager receives real-time notification on dashboard.
  4. SOC Manager reviews threat score (98%), AI summary, and approves the request.
  5. SOAR engine invokes Firewall API (IPTables/pfSense) to add `198.51.100.42` to blocklist.
  6. SOAR engine executes verification ping to confirm IP block.
  7. System appends action details and manager approval signature to Incident Audit Log.
  8. Incident status is updated to `CONTAINED`.
- **Extensions / Exception Flow:**
  - *4a. SOC Manager rejects request:* SOAR engine updates playbook status to `REJECTED`, logs reason, and notifies analyst.
  - *5a. Firewall API connection timeout:* SOAR engine attempts retry (3 attempts with exponential backoff). If failed, triggers rollback and notifies SysAdmin.
