#!/bin/bash

# ============================================================
# Inject Test Alert Data
# ============================================================
# Injects sample alerts into database for testing frontend display
# ============================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[⚠]${NC} $1"; }

echo ""
log_info "======================================"
log_info "Injecting Test Alert Data"
log_info "======================================"
echo ""

# Check if database is running
if ! docker-compose -f docker-compose.production.yml exec -T db pg_isready -U postgres &> /dev/null; then
    echo "✗ Database is not ready!"
    exit 1
fi

log_success "Database is ready"

# SQL to insert test data
SQL_FILE="/tmp/test_alerts.sql"

cat > "$SQL_FILE" << 'EOF'
-- Insert test alerts for frontend display testing
INSERT INTO wazuh_events (
    id, event_id, event_timestamp, agent_id, agent_name, manager,
    source_ip, source_port, source_user, source_country, source_city,
    dest_ip, dest_port, dest_user, dest_country,
    severity, rule_id, rule_description, rule_group, rule_level,
    message, category, risk_score, is_suppressed, wazuh_data
) VALUES
-- Critical alerts
(gen_random_uuid(), 'test-001', NOW() - INTERVAL '5 minutes', '001', 'web-server-01', 'wazuh-manager',
 '45.142.212.61', 45123, 'admin', 'CN', 'Beijing',
 '192.168.1.100', 22, NULL, 'VN',
 'critical', '5710', 'Multiple authentication failures detected', 'authentication', 12,
 'Feb 10 10:30:45 sshd[12345]: Failed password for admin from 45.142.212.61 port 45123 ssh2',
 'authentication', 95.0, false, '{}'),

(gen_random_uuid(), 'test-002', NOW() - INTERVAL '10 minutes', '002', 'db-server-01', 'wazuh-manager',
 '103.75.201.45', 51234, 'root', 'RU', 'Moscow',
 '192.168.1.101', 3306, NULL, 'VN',
 'critical', '5551', 'SQL injection attempt detected', 'web', 14,
 'SQL injection attempt: UNION SELECT * FROM users',
 'web_application_attack', 98.0, false, '{}'),

-- High severity alerts
(gen_random_uuid(), 'test-003', NOW() - INTERVAL '15 minutes', '001', 'web-server-01', 'wazuh-manager',
 '185.220.101.23', 44567, NULL, 'US', 'New York',
 '192.168.1.100', 80, NULL, 'VN',
 'high', '31100', 'Port scan detected', 'attack', 10,
 'Port scan from 185.220.101.23 targeting ports 80, 443, 22',
 'network_attack', 85.0, false, '{}'),

(gen_random_uuid(), 'test-004', NOW() - INTERVAL '20 minutes', '003', 'app-server-01', 'wazuh-manager',
 '198.51.100.45', 39876, 'hacker', 'KR', 'Seoul',
 '192.168.1.102', 443, NULL, 'VN',
 'high', '31106', 'Malware download attempt', 'malware', 11,
 'Malicious file download detected from suspicious domain',
 'malware', 88.0, false, '{}'),

-- Medium severity alerts
(gen_random_uuid(), 'test-005', NOW() - INTERVAL '25 minutes', '002', 'db-server-01', 'wazuh-manager',
 '203.0.113.67', 35421, NULL, 'DE', 'Berlin',
 '192.168.1.101', 3306, NULL, 'VN',
 'medium', '5402', 'User login at unusual time', 'authentication', 6,
 'User logged in outside business hours',
 'authentication', 55.0, false, '{}'),

(gen_random_uuid(), 'test-006', NOW() - INTERVAL '30 minutes', '001', 'web-server-01', 'wazuh-manager',
 '192.168.1.50', NULL, 'john', NULL, NULL,
 NULL, NULL, NULL, NULL,
 'medium', '5403', 'File integrity check failed', 'syscheck', 7,
 'File /etc/passwd was modified',
 'file_integrity_control', 60.0, false, '{}'),

-- Low severity alerts
(gen_random_uuid(), 'test-007', NOW() - INTERVAL '35 minutes', '004', 'mail-server-01', 'wazuh-manager',
 '192.168.1.200', NULL, NULL, NULL, NULL,
 NULL, NULL, NULL, NULL,
 'low', '1002', 'System information event', 'system', 3,
 'Service restarted successfully',
 'system', 20.0, false, '{}'),

(gen_random_uuid(), 'test-008', NOW() - INTERVAL '40 minutes', '001', 'web-server-01', 'wazuh-manager',
 '192.168.1.100', NULL, 'www-data', NULL, NULL,
 NULL, NULL, NULL, NULL,
 'low', '1003', 'Informational log entry', 'system', 2,
 'Apache server status: OK',
 'system', 15.0, false, '{}');

-- Update endpoint inventory
INSERT INTO endpoint_inventory (
    id, agent_id, agent_name, status, ip_address, os_name, os_version,
    current_risk_score, critical_alert_count, high_alert_count
) VALUES
(gen_random_uuid(), '001', 'web-server-01', 'active', '192.168.1.100', 'Ubuntu', '20.04', 90.0, 2, 1),
(gen_random_uuid(), '002', 'db-server-01', 'active', '192.168.1.101', 'Ubuntu', '22.04', 75.0, 1, 0),
(gen_random_uuid(), '003', 'app-server-01', 'active', '192.168.1.102', 'CentOS', '8', 60.0, 0, 1),
(gen_random_uuid(), '004', 'mail-server-01', 'active', '192.168.1.103', 'Debian', '11', 25.0, 0, 0)
ON CONFLICT (agent_id) DO UPDATE SET
    status = EXCLUDED.status,
    current_risk_score = EXCLUDED.current_risk_score,
    critical_alert_count = EXCLUDED.critical_alert_count,
    high_alert_count = EXCLUDED.high_alert_count;

EOF

log_info "Injecting test data into database..."

docker cp "$SQL_FILE" mini_soc_db_prod:/tmp/test_alerts.sql

docker-compose -f docker-compose.production.yml exec -T db \
    psql -U postgres -d mini_soc_prod -f /tmp/test_alerts.sql > /dev/null 2>&1

log_success "Test data injected successfully!"

rm "$SQL_FILE"

# Verify data
EVENT_COUNT=$(docker-compose -f docker-compose.production.yml exec -T db \
    psql -U postgres -d mini_soc_prod -tAc \
    "SELECT COUNT(*) FROM wazuh_events WHERE event_id LIKE 'test-%'" 2>/dev/null || echo "0")

log_success "Inserted $EVENT_COUNT test alerts"

echo ""
log_info "Test data breakdown:"
docker-compose -f docker-compose.production.yml exec -T db \
    psql -U postgres -d mini_soc_prod -c \
    "SELECT severity, COUNT(*) as count FROM wazuh_events WHERE event_id LIKE 'test-%' GROUP BY severity ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END" \
    2>/dev/null || echo "Could not fetch breakdown"

echo ""
log_success "======================================"
log_success "✅ Test Data Ready!"
log_success "======================================"
echo ""
echo "Now you can:"
echo "1. Open web UI and login"
echo "2. Check dashboard - should show 8 test alerts"
echo "3. Go to Alerts page - should see all test alerts"
echo "4. Filter by severity - should work correctly"
echo "5. Check agents page - should show 4 test servers"
echo ""
log_warn "To remove test data later:"
echo "docker-compose -f docker-compose.production.yml exec -T db psql -U postgres -d mini_soc_prod -c \"DELETE FROM wazuh_events WHERE event_id LIKE 'test-%'\""
echo ""
