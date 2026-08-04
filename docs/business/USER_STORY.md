# User Stories (Agile Standard)
## Enterprise Mini SOC Platform

### 1. User Story Index

| Story ID | Title | Priority | Target Epic |
| :--- | :--- | :--- | :--- |
| **US-001** | Real-time Alert Monitoring | Must Have | Monitoring |
| **US-002** | Threat Intel Ingestion & GeoIP | Must Have | Threat Intelligence |
| **US-003** | AI Incident Summarization | Should Have | AI Assistant |
| **US-004** | SOAR Playbook Execution with Approval | Must Have | SOAR Automation |
| **US-005** | Incident SLA & Lifecycle Tracking | Must Have | Incident Management |
| **US-006** | Zabbix Infrastructure Health Monitoring | Should Have | Monitoring |
| **US-007** | Asset Inventory & Criticality Mapping | Must Have | Asset Management |
| **US-008** | Executive SOC Analytics Dashboard | Should Have | Analytics |

---

### 2. User Story Specifications & Acceptance Criteria

#### US-001: Real-time Alert Monitoring
- **User Story:** As a Tier 1 SOC Analyst, I want to see real-time security alerts streamed immediately to my dashboard, so that I can quickly spot critical threats without refreshing the browser.
- **Acceptance Criteria (Gherkin):**
  - **Given** a SOC Analyst is logged into the Mini SOC Platform dashboard,
  - **When** a critical alert (e.g. Wazuh Rule 5710 - SSH Brute Force) is triggered by an endpoint agent,
  - **Then** the alert must appear in the live alert grid within 500ms via WebSocket, displaying severity badge, agent name, source IP, and MITRE Tactic.
  - **And** an audible alert notification sound should play for CRITICAL severity items.

#### US-002: Threat Intel Ingestion & GeoIP
- **User Story:** As a SOC Analyst, I want external IP addresses in alerts automatically enriched with GeoIP and Threat Intel reputation scores, so that I can immediately determine if an IP is a known malicious actor.
- **Acceptance Criteria (Gherkin):**
  - **Given** an alert containing an external IP `185.220.101.5`,
  - **When** the alert is processed by the ingestion engine,
  - **Then** the system queries the Threat Intel module (Redis cache -> VirusTotal / AbuseIPDB),
  - **And** attaches GeoIP location (Country, Flag, ISP) and reputation score (e.g. 95% Malicious) to the alert details panel.

#### US-003: AI Incident Summarization
- **User Story:** As a Tier 2 Analyst, I want an AI-generated concise summary and root-cause analysis for grouped alerts, so that I can reduce investigation time from 20 minutes to 2 minutes.
- **Acceptance Criteria (Gherkin):**
  - **Given** an incident containing 15 aggregated brute-force and privilege escalation alerts on Server-DB-01,
  - **When** I click "Analyze with AI",
  - **Then** the AI Security Assistant generates a short 3-bullet executive summary, probable root cause, and recommended containment steps.
  - **And** the AI Risk Score (0-100) is updated based on threat vector analysis.

#### US-004: SOAR Playbook Execution with Approval
- **User Story:** As an Incident Responder, I want to trigger a firewall blocking playbook for an attacking IP, with required manager approval, so that threats can be blocked quickly without risking unauthorized outages.
- **Acceptance Criteria (Gherkin):**
  - **Given** a validated malicious IP address in an active incident,
  - **When** an analyst initiates the "Block IP via Firewall" playbook,
  - **Then** a pending approval request is sent to the SOC Manager via dashboard notification,
  - **And** upon SOC Manager approval, the SOAR engine executes the firewall API call, records audit logs, and updates status to "Blocked".

#### US-005: Incident SLA & Lifecycle Tracking
- **User Story:** As a SOC Manager, I want to track incident response SLAs with visual countdown timers, so that our team meets organizational response targets.
- **Acceptance Criteria (Gherkin):**
  - **Given** a new CRITICAL incident is created,
  - **When** viewing the Incident Board,
  - **Then** a 30-minute containment SLA countdown timer is actively displayed,
  - **And** if the timer drops below 5 minutes without status change to `CONTAINED`, the incident card highlights in flashing red and escalates to the SOC Manager.
