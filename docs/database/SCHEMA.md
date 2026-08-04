# Relational Schema Specification (PostgreSQL 16)
## Enterprise Mini SOC Platform

### 1. DDL Schema Definition (Standardized 3NF)

```sql
-- 1. Roles & Users
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Assets
CREATE TABLE assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hostname VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET NOT NULL,
    asset_type VARCHAR(50) NOT NULL, -- SERVER, WORKSTATION, FIREWALL
    criticality VARCHAR(20) DEFAULT 'MEDIUM' NOT NULL, -- LOW, MEDIUM, HIGH, CRITICAL
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. Partitioned Alerts Table
CREATE TABLE alerts (
    id UUID DEFAULT gen_random_uuid(),
    wazuh_rule_id VARCHAR(50) NOT NULL,
    title VARCHAR(500) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- LOW, MEDIUM, HIGH, CRITICAL
    severity_level INT NOT NULL,
    source_ip INET,
    asset_id UUID REFERENCES assets(id) ON DELETE SET NULL,
    ioc_data JSONB DEFAULT '{}'::jsonb NOT NULL,
    threat_intel JSONB DEFAULT '{}'::jsonb NOT NULL,
    mitre_tactic VARCHAR(100),
    mitre_technique VARCHAR(100),
    timestamp TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Monthly Partitions
CREATE TABLE alerts_y2026m08 PARTITION OF alerts
    FOR VALUES FROM ('2026-08-01 00:00:00+00') TO ('2026-09-01 00:00:00+00');

-- 4. Incidents
CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_number VARCHAR(50) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    status VARCHAR(30) DEFAULT 'NEW' NOT NULL, -- NEW, IN_PROGRESS, CONTAINED, RESOLVED, CLOSED
    severity VARCHAR(20) NOT NULL,
    assigned_to_id UUID REFERENCES users(id) ON DELETE SET NULL,
    sla_expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMPTZ
);

-- 5. Audit Logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(255),
    ip_address INET,
    details JSONB DEFAULT '{}'::jsonb NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```
