# NIST SP 800-61 Incident Response Playbook & PIR Template
## Enterprise Mini SOC Platform

### 1. NIST SP 800-61 Incident Lifecycle Stages

```
┌─────────────────────────────────────────────────────────────┐
│             NIST SP 800-61 Incident Response Flow           │
│                                                             │
│  1. Preparation         --> Pre-configured Wazuh & Playbooks│
│  2. Detection & Analysis--> Alert correlation & Threat Intel│
│  3. Containment         --> SOAR Firewall block & isolation │
│  4. Eradication         --> Malicious process/user termination│
│  5. Recovery            --> System validation & service restore│
│  6. Post-Incident Review--> Lessons learned report          │
└─────────────────────────────────────────────────────────────┘
```

---

### 2. Forensic Evidence Collection Standard
1. **Volatile Memory & Network:** Capture netstat connections, active process trees, and open handles prior to host shutdown.
2. **Hash Integrity:** Calculate SHA256 hashes for all exported forensic artifacts (logs, memory dumps).
3. **Chain of Custody:** Record analyst ID, exact timestamp, and storage location in immutable DB audit logs (BR-004).

---

### 3. Post-Incident Review (PIR) Report Structure
- **Incident Overview:** Ticket ID, Severity, Affected Assets, Root Cause Summary.
- **Incident Timeline:** Sequence of events from Initial Access to Containment.
- **Mitigation & Corrective Actions:** SOAR playbooks executed, firewall rules added.
- **Lessons Learned & Recommendations:** Detection rule tuning to prevent recurrence.
