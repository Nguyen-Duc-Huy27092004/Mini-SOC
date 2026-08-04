# Database Indexing Strategy & Query Optimization
## Enterprise Mini SOC Platform

### 1. Mandatory Foreign Key & Query Indexing

```sql
-- Indexes for High-Frequency Alert Filtering
CREATE INDEX idx_alerts_timestamp_severity ON alerts (timestamp DESC, severity);
CREATE INDEX idx_alerts_source_ip ON alerts (source_ip);
CREATE INDEX idx_alerts_asset_id ON alerts (asset_id);
CREATE INDEX idx_alerts_mitre_tactic ON alerts (mitre_tactic);

-- JSONB GIN Indexes for Fast IOC & Threat Intel Lookup
CREATE INDEX idx_alerts_ioc_data_gin ON alerts USING GIN (ioc_data);
CREATE INDEX idx_alerts_threat_intel_gin ON alerts USING GIN (threat_intel);

-- Incident & Audit Indexes
CREATE INDEX idx_incidents_status_severity ON incidents (status, severity);
CREATE INDEX idx_incidents_assigned_to ON incidents (assigned_to_id);
CREATE INDEX idx_audit_logs_user_action ON audit_logs (user_id, action, created_at DESC);
```
