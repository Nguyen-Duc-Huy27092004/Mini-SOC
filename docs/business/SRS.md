# Software Requirements Specification (SRS)
## Enterprise Mini SOC Platform

### 1. Introduction
This Software Requirements Specification (SRS) details the functional and non-functional requirements for the Enterprise Mini SOC Platform.

---

### 2. Functional Requirements Breakdown

#### 2.1 Alert Monitoring & Ingestion (FR-MON)
- **FR-MON-001:** Real-time ingestion of Wazuh security events via WebSocket / JSON log stream.
- **FR-MON-002:** Infrastructure metric collection via Zabbix API (Host status, CPU/RAM utilization, Disk IO).
- **FR-MON-003:** Alert deduplication and aggregation within a rolling 60-second window to prevent alert fatigue.
- **FR-MON-004:** Real-time alert streaming to Frontend via WebSockets with latency < 500ms.

#### 2.2 Threat Intelligence & Enrichment (FR-TI)
- **FR-TI-001:** Automated IOC extraction (IPv4, IPv6, SHA256, MD5, Domain) from incoming security alerts.
- **FR-TI-002:** Multi-provider Threat Intel lookups: VirusTotal API, AbuseIPDB API, and AlienVault OTX.
- **FR-TI-003:** GeoIP lookup and visualization (Country, City, ISP, ASN, Latitude/Longitude).
- **FR-TI-004:** Threat Intel caching in Redis (TTL: 24 hours) to respect provider API rate limits.

#### 2.3 AI Security Assistant (FR-AI)
- **FR-AI-001:** Automated natural-language alert summarization for Tier 1 SOC analysts.
- **FR-AI-002:** Incident correlation grouping related alerts into a single cohesive incident story.
- **FR-AI-003:** Root cause recommendation based on attack vectors and past incident patterns.
- **FR-AI-004:** Composite Risk Score calculation combining Wazuh severity, TI reputation, asset criticality, and AI confidence.

#### 2.4 SOAR Playbooks & Automation (FR-SOAR)
- **FR-SOAR-001:** Playbook trigger engine supporting automated and manual execution.
- **FR-SOAR-002:** Pre-defined Playbooks:
  - *Playbook-01:* Firewall IP Blocking (pfSense / IPTables API integration).
  - *Playbook-02:* Wazuh Active Response Host Isolation.
  - *Playbook-03:* User Account Suspension.
- **FR-SOAR-003:** Approval Gate Workflow: Any destructive action requires explicit authorization from a SOC Manager / Lead.
- **FR-SOAR-004:** Automated rollback capability for failed or reversed playbook actions.

#### 2.5 Incident & Asset Management (FR-INC & FR-AST)
- **FR-INC-001:** Ticket creation, lifecycle state transitions (`NEW`, `IN_PROGRESS`, `CONTAINED`, `RESOLVED`, `CLOSED`), and analyst assignment.
- **FR-INC-002:** SLA tracker with visual countdown timer based on severity.
- **FR-INC-003:** Post-Incident Review (PIR) report generator exporting PDF / Markdown reports.
- **FR-AST-001:** Asset inventory listing registered servers, IP addresses, criticalities, and associated security agent statuses.

---

### 3. Non-Functional Requirements (NFR)

#### 3.1 Performance & Scalability (NFR-PERF)
- **NFR-PERF-001 (Ingestion Throughput):** Backend must ingest and process up to 1,000 alerts per second under peak load.
- **NFR-PERF-002 (API Latency):** 95th percentile REST API response time must be under 200ms for read operations.
- **NFR-PERF-003 (Dashboard FPS):** Frontend rendering must maintain 60 FPS under continuous WebSocket update streams.

#### 3.2 Security & Zero Trust (NFR-SEC)
- **NFR-SEC-001 (Authentication):** OAuth2 / JWT authentication with mandatory password complexity and short-lived access tokens (15 mins) + refresh tokens.
- **NFR-SEC-002 (Role-Based Access Control - RBAC):** Strictly enforced roles: `Admin`, `SOC_Manager`, `SOC_Analyst_T2`, `SOC_Analyst_T1`, `Read_Only`.
- **NFR-SEC-003 (TLS Encryption):** HTTPS / WSS mandatory with TLS 1.3 across all endpoints.
- **NFR-SEC-004 (OWASP API Top 10):** Input validation on all endpoints using Pydantic V2 schemas, strict CORS, rate limiting, and SQL injection prevention via SQLAlchemy ORM.

#### 3.3 Reliability & Availability (NFR-REL)
- **NFR-REL-001 (Uptime):** System availability target of 99.9% uptime.
- **NFR-REL-002 (Data Resilience):** PostgreSQL WAL archiving and Redis persistence (RDB + AOF).
- **NFR-REL-003 (Graceful Degradation):** If external Threat Intel APIs fail or hit rate limits, local caching and fallback heuristics must allow alert processing to continue seamlessly.

---

### 4. Data Constraints & Requirements
- **Database:** PostgreSQL 16+ with partitioning for alert tables by month.
- **Cache / Message Queue:** Redis 7+ for PubSub and rate-limit tracking.
- **Retention Policy:** Hot alert storage retained for 90 days; cold archive retained for 365 days.
