# SOC Standard Operating Procedure (SOP) & Alert Triage
## Enterprise Mini SOC Platform

### 1. Alert Triage Workflow (Tier 1 & Tier 2)

```
[ Ingested Alert Trigger ]
           │
           ▼
[ Check Severity & TI Score ]
           │
  ┌────────┴────────┐
  │                 │
[ CRITICAL / HIGH ] [ MEDIUM / LOW ]
  │                 │
  ▼                 ▼
[ Immediate Triage  [ Queue for Standard
  SLA: 5 mins ]       Shift Review ]
  │                 │
  └────────┬────────┘
           ▼
[ Check False Positive Rules ]
           │
  ┌────────┴────────┐
  │                 │
[ Valid Threat ]   [ False Positive ]
  │                 │
  ▼                 ▼
[ Create Incident   [ Close Alert & Update
  Ticket & Run        Deduplication Filter ]
  SOAR Playbook ]
```

---

### 2. SLA Commitment Targets
- **Critical Severity:** Acknowledge within **5 minutes**; Contain within **30 minutes**.
- **High Severity:** Acknowledge within **15 minutes**; Contain within **2 hours**.
- **Medium / Low Severity:** Acknowledge within **1 hour**; Resolve within **24 hours**.
