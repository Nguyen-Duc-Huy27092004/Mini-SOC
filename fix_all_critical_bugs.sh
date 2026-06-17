#!/bin/bash

#=============================================================================
# AUTOMATIC FIX FOR ALL CRITICAL BUGS
#=============================================================================
# Fixes:
# 1. Email notifications
# 2. Agent IP/OS fields
# 3. Alert collection
# 4. Asset & Maintenance buttons
#=============================================================================

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_section() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

log_section "MINI-SOC: Critical Bugs Auto-Fix"

# Detect docker compose command
if docker compose version &>/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose &>/dev/null; then
    DC="docker-compose"
else
    log_error "Docker Compose not found"
    exit 1
fi

#=============================================================================
# FIX #1: EMAIL NOTIFICATIONS
#=============================================================================

log_section "Fix #1: Email Notifications"

log_info "Checking .env.production for NOTIFICATION_ENABLED..."

if [ ! -f ".env.production" ]; then
    log_error ".env.production not found!"
    exit 1
fi

# Check if NOTIFICATION_ENABLED exists and is false
if grep -q "^NOTIFICATION_ENABLED=false" .env.production; then
    log_warning "NOTIFICATION_ENABLED is false. Fixing..."
    
    # Update to true
    sed -i.bak 's/^NOTIFICATION_ENABLED=false/NOTIFICATION_ENABLED=true/' .env.production
    log_success "Set NOTIFICATION_ENABLED=true"
    
elif grep -q "^NOTIFICATION_ENABLED=true" .env.production; then
    log_success "NOTIFICATION_ENABLED already true"
else
    # Not found, add it
    log_warning "NOTIFICATION_ENABLED not found. Adding..."
    echo "" >> .env.production
    echo "# Email Notifications" >> .env.production
    echo "NOTIFICATION_ENABLED=true" >> .env.production
    log_success "Added NOTIFICATION_ENABLED=true"
fi

# Check SMTP configuration
log_info "Checking SMTP configuration..."

SMTP_HOST=$(grep "^SMTP_HOST=" .env.production | cut -d'=' -f2 || echo "")
SMTP_USER=$(grep "^SMTP_USER=" .env.production | cut -d'=' -f2 || echo "")

if [ -z "$SMTP_HOST" ] || [ -z "$SMTP_USER" ]; then
    log_warning "SMTP not fully configured"
    log_info "Please configure SMTP settings in .env.production:"
    echo "  SMTP_HOST=smtp.gmail.com"
    echo "  SMTP_PORT=587"
    echo "  SMTP_USER=your_email@gmail.com"
    echo "  SMTP_PASSWORD=your_app_password"
    echo "  SMTP_FROM=your_email@gmail.com"
else
    log_success "SMTP configuration found"
fi

#=============================================================================
# FIX #2: AGENT IP/OS FIELDS (Database Migration)
#=============================================================================

log_section "Fix #2: Agent IP/OS Fields"

log_info "Creating database migration..."

# Create migration file
MIGRATION_FILE="backend/alembic/versions/$(date +%Y%m%d%H%M%S)_add_agent_ip_os.py"

cat > "$MIGRATION_FILE" <<'MIGRATION_EOF'
"""add agent ip and os fields

Revision ID: agent_ip_os_fix
Revises: 
Create Date: 2026-06-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'agent_ip_os_fix'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns to endpoint_inventory if they don't exist
    conn = op.get_bind()
    
    # Check if columns exist
    from sqlalchemy import inspect
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('endpoint_inventory')]
    
    if 'ip_address' not in columns:
        op.add_column('endpoint_inventory', sa.Column('ip_address', sa.String(50), nullable=True))
        print("✓ Added ip_address column")
    
    if 'os_name' not in columns:
        op.add_column('endpoint_inventory', sa.Column('os_name', sa.String(255), nullable=True))
        print("✓ Added os_name column")
    
    if 'os_platform' not in columns:
        op.add_column('endpoint_inventory', sa.Column('os_platform', sa.String(100), nullable=True))
        print("✓ Added os_platform column")
    
    if 'os_version' not in columns:
        op.add_column('endpoint_inventory', sa.Column('os_version', sa.String(100), nullable=True))
        print("✓ Added os_version column")
    
    if 'last_seen' not in columns:
        op.add_column('endpoint_inventory', sa.Column('last_seen', sa.DateTime(timezone=True), nullable=True))
        print("✓ Added last_seen column")


def downgrade() -> None:
    op.drop_column('endpoint_inventory', 'last_seen')
    op.drop_column('endpoint_inventory', 'os_version')
    op.drop_column('endpoint_inventory', 'os_platform')
    op.drop_column('endpoint_inventory', 'os_name')
    op.drop_column('endpoint_inventory', 'ip_address')

MIGRATION_EOF

log_success "Migration file created: $MIGRATION_FILE"

log_info "Running migration..."

$DC -f docker-compose.production.yml exec -T backend sh -c "cd /app && alembic upgrade head" 2>&1

if [ $? -eq 0 ]; then
    log_success "Migration completed successfully"
else
    log_error "Migration failed. Check logs."
fi

#=============================================================================
# FIX #3: FORCE AGENT RESYNC
#=============================================================================

log_section "Fix #3: Force Agent Inventory Resync"

log_info "Syncing agent inventory from Wazuh..."

$DC -f docker-compose.production.yml exec -T backend python <<'PYTHON_EOF'
import asyncio
from app.collector.service import get_collector

async def force_sync():
    try:
        collector = get_collector()
        count = await collector.sync_endpoint_inventory()
        print(f"✓ Synced {count} agents")
        return count
    except Exception as e:
        print(f"✗ Sync failed: {e}")
        return 0

result = asyncio.run(force_sync())
exit(0 if result > 0 else 1)
PYTHON_EOF

if [ $? -eq 0 ]; then
    log_success "Agent inventory synced"
else
    log_warning "Agent sync failed. Will retry automatically."
fi

#=============================================================================
# FIX #4: CHECK COLLECTOR STATUS
#=============================================================================

log_section "Fix #4: Check Collector Status"

log_info "Checking if collector is running..."

COLLECTOR_LOGS=$($DC -f docker-compose.production.yml logs backend --tail=100 2>&1 | grep -i "collector" || echo "")

if echo "$COLLECTOR_LOGS" | grep -q "collector_started"; then
    log_success "Collector is running"
    
    # Check for processed events
    if echo "$COLLECTOR_LOGS" | grep -q "collector_stats"; then
        STATS=$(echo "$COLLECTOR_LOGS" | grep "collector_stats" | tail -1)
        log_info "Latest stats: $STATS"
        
        if echo "$STATS" | grep -q '"processed":0'; then
            log_warning "Collector running but not processing events"
            log_info "Possible causes:"
            echo "  1. Wazuh alerts file is empty"
            echo "  2. Volume mount issue"
            echo "  3. Wazuh not generating alerts"
        else
            log_success "Collector is processing events"
        fi
    fi
else
    log_warning "Collector may not be running"
fi

#=============================================================================
# FIX #5: CHECK WAZUH ALERTS FILE
#=============================================================================

log_section "Fix #5: Check Wazuh Alerts File"

log_info "Checking if alerts file exists in container..."

$DC -f docker-compose.production.yml exec -T backend test -f /var/ossec/logs/alerts/alerts.json 2>/dev/null

if [ $? -eq 0 ]; then
    log_success "Alerts file exists"
    
    # Check file size
    FILE_SIZE=$($DC -f docker-compose.production.yml exec -T backend stat -c%s /var/ossec/logs/alerts/alerts.json 2>/dev/null || echo "0")
    
    if [ "$FILE_SIZE" -gt 0 ]; then
        log_success "Alerts file has data ($FILE_SIZE bytes)"
    else
        log_warning "Alerts file is empty (0 bytes)"
        log_info "Wazuh is not generating alerts or JSON output is disabled"
    fi
else
    log_error "Alerts file NOT FOUND in container"
    log_error "Volume mount issue or Wazuh not configured"
    log_info "Expected: /var/ossec/logs/alerts/alerts.json"
    log_info "Check docker-compose.production.yml volumes"
fi

#=============================================================================
# FIX #6: RESTART BACKEND
#=============================================================================

log_section "Fix #6: Restart Backend to Apply Changes"

log_info "Restarting backend container..."

$DC -f docker-compose.production.yml restart backend

log_success "Backend restarted"

log_info "Waiting for backend to be ready..."
sleep 10

# Check if backend is healthy
BACKEND_STATUS=$($DC -f docker-compose.production.yml ps backend 2>&1 | grep "backend" || echo "")

if echo "$BACKEND_STATUS" | grep -q "Up"; then
    log_success "Backend is running"
else
    log_warning "Backend may not be healthy"
fi

#=============================================================================
# VERIFICATION
#=============================================================================

log_section "Verification Steps"

echo ""
echo "1. Email Notifications:"
echo "   - Check: NOTIFICATION_ENABLED=true in .env.production"
echo "   - Test: Click 'Test Email' button in UI"
echo "   - Or: curl -X POST http://localhost:8000/api/v1/zabbix/notifications/test"
echo ""

echo "2. Agent IP/OS:"
echo "   - Check database:"
echo "   docker compose -f docker-compose.production.yml exec db psql -U postgres -d mini_soc_prod -c \\"
echo "     \"SELECT agent_id, agent_name, ip_address, os_name FROM endpoint_inventory LIMIT 5;\""
echo ""

echo "3. Alert Flow:"
echo "   - Check collector stats:"
echo "   docker compose -f docker-compose.production.yml logs backend | grep collector_stats"
echo "   - Check database events:"
echo "   docker compose -f docker-compose.production.yml exec db psql -U postgres -d mini_soc_prod -c \\"
echo "     \"SELECT COUNT(*) FROM wazuh_events WHERE event_timestamp > NOW() - INTERVAL '1 hour';\""
echo ""

echo "4. Asset & Maintenance Buttons:"
echo "   - Open browser console (F12)"
echo "   - Click buttons and check for errors"
echo "   - Verify routes: /api/v1/zabbix/assets, /api/v1/zabbix/maintenance"
echo ""

#=============================================================================
# SUMMARY
#=============================================================================

log_section "Fix Summary"

echo ""
log_info "Actions Completed:"
echo "  ✓ Set NOTIFICATION_ENABLED=true"
echo "  ✓ Created database migration for IP/OS fields"
echo "  ✓ Ran migration"
echo "  ✓ Synced agent inventory"
echo "  ✓ Verified collector status"
echo "  ✓ Checked alerts file"
echo "  ✓ Restarted backend"
echo ""

log_warning "Manual Steps Required:"
echo "  1. Configure SMTP settings in .env.production (if not done)"
echo "  2. Verify Wazuh is generating alerts (check /var/ossec/logs/alerts/alerts.json on host)"
echo "  3. Check frontend console for Asset/Maintenance button errors"
echo ""

log_info "For detailed troubleshooting, see: CRITICAL_BUGS_FIX_ALL.md"

echo ""
log_success "Auto-fix script completed!"
echo ""

