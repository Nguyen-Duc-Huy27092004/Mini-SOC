# Data Retention & Partition Maintenance
## Enterprise Mini SOC Platform

### 1. Retention Policy Framework
- **Hot Alert Storage (PostgreSQL):** Retained for 90 days across 3 monthly table partitions (`alerts_y2026m08`, etc.).
- **Cold Storage Archive:** Monthly partitions older than 90 days are detached via `ALTER TABLE alerts DETACH PARTITION` and exported to compressed JSON archives stored on backup volume before partition drop.
- **Audit Logs:** Preserved in hot database for 365 days minimum (compliance mandate).
