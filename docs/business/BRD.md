# Business Requirements Document (BRD)
## Enterprise Mini SOC Platform

### 1. Document Control
- **Project Name:** Enterprise Mini SOC Platform
- **Version:** 1.1.0
- **Author:** 01 Business Analyst Agent
- **Status:** Approved for Architectural Handoff
- **Target Audience:** Product Owner, Solution Architect, Security Architect, Key Stakeholders

---

### 2. Business Goal & Executive Summary
The primary objective of the **Enterprise Mini SOC Platform** is to deliver a production-grade, highly scalable, zero-trust Security Operations Center (SOC) platform tailored for small-to-medium enterprises (SMEs) and managed security service providers (MSSPs). 

The system unifies:
1. **Real-time Security & IDS/IPS Monitoring** (Wazuh API, Suricata IDS, Zeek log streams)
2. **Instant Automated & Manual Anti-DDoS Mitigation** (HTTP/HTTPS Flood, SYN/UDP/ICMP Flood, Slowloris)
3. **Infrastructure Health & Performance Monitoring** (Zabbix API)
4. **Threat Intelligence Enrichment** (VirusTotal, AbuseIPDB, AlienVault OTX, Spamhaus)
5. **AI-Driven Correlation & Investigation** (Root Cause Analysis & Threat Summarization)
6. **Automated SOAR Execution** (Instant DDoS Auto-Block & Approval-gated playbooks)
7. **Incident Response Lifecycle Management** (NIST SP 800-61 aligned)

---

### 3. Key Stakeholders

| Stakeholder Role | Responsibilities | Key Business Value Needed |
| :--- | :--- | :--- |
| **Chief Information Security Officer (CISO)** | Oversight of security posture, compliance, and risk | Executive reporting, compliance metrics, MTTR/MTTD reduction |
| **SOC Manager / Lead** | Daily SOC operations, shift management, SLA tracking | Unified dashboard, triage queues, team performance metrics |
| **Tier 1 / Tier 2 SOC Analyst** | Monitoring, triage, initial investigation, alert validation | Fast correlation, enrichment context, AI summaries, false positive reduction |

---

### 4. Business Rules (BR)

- **BR-001 (Zero Autonomous Destructive Action - General):** AI and general automation models shall NEVER execute disruptive security actions (e.g. terminating server, revoking admin credentials) autonomously without human approval.
- **BR-001.1 (Anti-DDoS Automated Blocking Exemption):** High-confidence DDoS attacks ($\ge 85\%$ score from Suricata/Zeek or Correlation Engine) are EXEMPT from human approval wait times. Upon detection, the SOAR engine SHALL **automatically block attacking source IPs instantly** via Firewall & Nginx rate limit APIs to guarantee service availability. Manual 1-click override controls remain accessible on analyst dashboards.
- **BR-002 (Alert Severity Mapping):** Every ingested alert MUST be mapped to standard severity levels: `CRITICAL` (Level 12-15), `HIGH` (Level 9-11), `MEDIUM` (Level 5-8), and `LOW` (Level 1-4).
- **BR-003 (MITRE ATT&CK Alignment):** All security alerts and incidents MUST be tagged with corresponding MITRE ATT&CK Tactic and Technique IDs.
- **BR-004 (Audit Non-Repudiation):** All user activities, SOC analyst actions, and SOAR playbook runs MUST generate immutable audit logs preserved for a minimum of 365 days.
