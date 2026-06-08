#!/bin/bash

# ============================================================
# End-to-End Data Flow Validation
# ============================================================
# Validates: Wazuh → Collector → DB → API → Frontend
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[⚠]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_step() { echo -e "\n${CYAN}═══ $1 ═══${NC}\n"; }

NGINX_PORT=${NGINX_PORT:-2709}
BASE_URL="http://localhost:$NGINX_PORT"

echo ""
log_step "END-TO-END DATA FLOW VALIDATION"

# ============================================================
# STEP 1: CHECK WAZUH ALERTS FILE
# ============================================================

log_step "1. Wazuh Alerts Source"

ALERTS_FILE="/var/ossec/logs/alerts/alerts.json"

if [ -f "$ALERTS_FILE" ]; then
    log_success "Wazuh alerts file exists: $ALERTS_FILE"
    
    # Check if file is being written
    SIZE_BEFORE=$(stat -c%s "$ALERTS_FILE" 2>/dev/null || echo "0")
    log_info "Current file size: $SIZE_BEFORE bytes"
    
    log_info "Waiting 5 seconds to check if file is growing..."
    sleep 5
    
    SIZE_AFTER=$(stat -c%s "$ALERTS_FILE" 2>/dev/null || echo "0")
    log_info "New file size: $SIZE_AFTER bytes"
    
    if [ "$SIZE_AFTER" -gt "$SIZE_BEFORE" ]; then
        log_success "✓ Wazuh is actively writing alerts"
        GROWTH=$((SIZE_AFTER - SIZE_BEFORE))
        log_info "  Growth: +${GROWTH} bytes in 5 seconds"
    else
        log_warn "⚠ File size unchanged - Wazuh may not be generating alerts"
        log_info "  Solution: Trigger test alerts with: sudo /var/ossec/bin/agent_control -r -a"
    fi
    
    # Show last 3 alerts
    echo ""
    log_info "Last 3 alerts in file:"
    tail -n 3 "$ALERTS_FILE" | while read line; do
        if [ -n "$line" ]; then
            RULE_ID=$(echo "$line" | jq -r '.rule.id // "N/A"' 2>/dev/null || echo "N/A")
            LEVEL=$(echo "$line" | jq -r '.rule.level // "N/A"' 2>/dev/null || echo "N/A")
            AGENT=$(echo "$line" | jq -r '.agent.name // "N/A"' 2>/dev/null || echo "N/A")
            echo "  - Rule $RULE_ID (level $LEVEL) from $AGENT"
        fi
    done
    
else
    log_error "✗ Wazuh alerts file NOT FOUND: $ALERTS_FILE"
    log_info "  Solutions:"
    echo "    1. Check Wazuh is installed: systemctl status wazuh-manager"
    echo "    2. Configure alerting: /var/ossec/etc/ossec.conf"
    echo "    3. Use Wazuh API fallback (if configured)"
    exit 1
fi

# ============================================================
# STEP 2: CHECK COLLECTOR STATUS
# ============================================================

log_step "2. Collector Service"

log_info "Checking collector container..."
if docker ps --filter "name=mini_soc_backend_prod" --filter "status=running" | grep -q mini_soc_backend; then
    log_success "✓ Backend container is running"
    
    # Check collector logs
    log_info "Checking collector logs (last 50 lines)..."
    COLLECTOR_LOGS=$(docker-compose -f docker-compose.production.yml logs --tail 50 backend 2>/dev/null | grep -i "collector" || echo "")
    
    if echo "$COLLECTOR_LOGS" | grep -q "collector_started"; then
        log_success "✓ Collector service started"
    else
        log_warn "⚠ Collector start message not found"
    fi
    
    if echo "$COLLECTOR_LOGS" | grep -q "tailer_started"; then
        log_success "✓ Alert tailer started"
        TAILER_FILE=$(echo "$COLLECTOR_LOGS" | grep "tailer_started" | tail -1 | grep -oP 'file=\K[^ ]+' || echo "")
        log_info "  Tailing: $TAILER_FILE"
    else
        log_warn "⚠ Tailer start message not found"
    fi
    
    if echo "$COLLECTOR_LOGS" | grep -q "alerts_batch_processed\|event_processed"; then
        log_success "✓ Collector is processing alerts"
        COUNT=$(echo "$COLLECTOR_LOGS" | grep -c "event_processed" || echo "0")
        log_info "  Processed events in last 50 logs: $COUNT"
    else
        log_warn "⚠ No processed events found in recent logs"
        log_info "  This may be normal if no new alerts since startup"
    fi
    
    # Check for errors
    ERRORS=$(docker-compose -f docker-compose.production.yml logs --tail 100 backend 2>/dev/null | grep -iE "error|exception|failed|traceback" | grep -i collector || echo "")
    if [ -n "$ERRORS" ]; then
        log_error "✗ Found collector errors:"
        echo "$ERRORS" | head -5
    else
        log_success "✓ No collector errors in recent logs"
    fi
    
else
    log_error "✗ Backend container not running!"
    exit 1
fi

# ============================================================
# STEP 3: CHECK DATABASE
# ============================================================

log_step "3. Database Storage"

log_info "Querying WazuhEvent table..."

EVENT_COUNT=$(docker-compose -f docker-compose.production.yml exec -T db \
    psql -U postgres -d mini_soc_prod -tAc \
    "SELECT COUNT(*) FROM wazuh_events WHERE is_suppressed = false" 2>/dev/null || echo "0")

RECENT_COUNT=$(docker-compose -f docker-compose.production.yml exec -T db \
    psql -U postgres -d mini_soc_prod -tAc \
    "SELECT COUNT(*) FROM wazuh_events WHERE event_timestamp > NOW() - INTERVAL '1 hour' AND is_suppressed = false" 2>/dev/null || echo "0")

TODAY_COUNT=$(docker-compose -f docker-compose.production.yml exec -T db \
    psql -U postgres -d mini_soc_prod -tAc \
    "SELECT COUNT(*) FROM wazuh_events WHERE event_timestamp > NOW() - INTERVAL '24 hours' AND is_suppressed = false" 2>/dev/null || echo "0")

echo "Total events in DB:      $EVENT_COUNT"
echo "Events (last hour):      $RECENT_COUNT"
echo "Events (last 24h):       $TODAY_COUNT"

if [ "$EVENT_COUNT" -gt 0 ]; then
    log_success "✓ Database has $EVENT_COUNT events"
    
    if [ "$RECENT_COUNT" -gt 0 ]; then
        log_success "✓ Recent activity detected ($RECENT_COUNT events in last hour)"
    else
        log_warn "⚠ No events in last hour (may be normal)"
    fi
    
    # Show sample data
    echo ""
    log_info "Sample of recent events:"
    docker-compose -f docker-compose.production.yml exec -T db \
        psql -U postgres -d mini_soc_prod -c \
        "SELECT event_timestamp, severity, category, agent_name, rule_id FROM wazuh_events ORDER BY event_timestamp DESC LIMIT 5" \
        2>/dev/null || log_warn "Could not fetch sample data"
        
else
    log_error "✗ Database is EMPTY - no events collected!"
    log_info "  Possible causes:"
    echo "    1. Collector not running properly"
    echo "    2. Wazuh not generating alerts"
    echo "    3. File permissions issue"
    echo "    4. Migration not applied"
fi

# ============================================================
# STEP 4: TEST API ENDPOINTS
# ============================================================

log_step "4. API Endpoints"

log_info "Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/api/v1/health/ready" 2>/dev/null)
HEALTH_CODE=$(echo "$HEALTH_RESPONSE" | grep "HTTP_CODE" | cut -d':' -f2)

if [ "$HEALTH_CODE" = "200" ]; then
    log_success "✓ Health endpoint OK"
else
    log_error "✗ Health endpoint failed (HTTP $HEALTH_CODE)"
fi

# Test alerts endpoint (requires auth)
echo ""
log_info "Testing alerts API (will show 401 if not authenticated)..."
ALERTS_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/api/v1/alerts?page=1&page_size=1" 2>/dev/null)
ALERTS_CODE=$(echo "$ALERTS_RESPONSE" | grep "HTTP_CODE" | cut -d':' -f2)
ALERTS_BODY=$(echo "$ALERTS_RESPONSE" | grep -v "HTTP_CODE")

if [ "$ALERTS_CODE" = "401" ]; then
    log_warn "⚠ Alerts API requires authentication (401) - this is expected"
    log_info "  Login via web UI to test full data flow"
elif [ "$ALERTS_CODE" = "200" ]; then
    log_success "✓ Alerts API responded successfully"
    
    ALERT_COUNT=$(echo "$ALERTS_BODY" | jq -r '.total // 0' 2>/dev/null || echo "0")
    log_info "  Total alerts in API response: $ALERT_COUNT"
    
    if [ "$ALERT_COUNT" -gt 0 ]; then
        log_success "✓ API is returning alert data"
    else
        log_warn "⚠ API returned 0 alerts (database may be empty)"
    fi
else
    log_error "✗ Alerts API failed (HTTP $ALERTS_CODE)"
fi

# Test dashboard endpoint
echo ""
log_info "Testing dashboard API..."
DASH_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/api/v1/dashboard" 2>/dev/null)
DASH_CODE=$(echo "$DASH_RESPONSE" | grep "HTTP_CODE" | cut -d':' -f2)

if [ "$DASH_CODE" = "401" ]; then
    log_warn "⚠ Dashboard API requires authentication (401)"
elif [ "$DASH_CODE" = "200" ]; then
    log_success "✓ Dashboard API responded successfully"
    
    DASH_BODY=$(echo "$DASH_RESPONSE" | grep -v "HTTP_CODE")
    ALERTS_TODAY=$(echo "$DASH_BODY" | jq -r '.summary.alerts_today // 0' 2>/dev/null || echo "0")
    log_info "  Alerts today (from dashboard): $ALERTS_TODAY"
else
    log_error "✗ Dashboard API failed (HTTP $DASH_CODE)"
fi

# ============================================================
# STEP 5: CHECK REDIS PUB/SUB
# ============================================================

log_step "5. Realtime Publishing (Redis)"

log_info "Checking Redis connection..."
if docker-compose -f docker-compose.production.yml exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    log_success "✓ Redis is responding"
    
    # Check active channels
    CHANNELS=$(docker-compose -f docker-compose.production.yml exec -T redis \
        redis-cli PUBSUB CHANNELS 2>/dev/null | grep "soc:" || echo "")
    
    if [ -n "$CHANNELS" ]; then
        log_success "✓ Redis pub/sub channels active:"
        echo "$CHANNELS" | while read ch; do
            echo "    - $ch"
        done
    else
        log_warn "⚠ No active pub/sub channels (may be normal if no subscribers)"
    fi
    
else
    log_error "✗ Redis not responding"
fi

# ============================================================
# STEP 6: FRONTEND ACCESS
# ============================================================

log_step "6. Frontend Access"

log_info "Testing frontend availability..."
FRONTEND_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/" 2>/dev/null)
FRONTEND_CODE=$(echo "$FRONTEND_RESPONSE" | grep "HTTP_CODE" | cut -d':' -f2)

if [ "$FRONTEND_CODE" = "200" ]; then
    log_success "✓ Frontend is accessible"
    log_info "  URL: $BASE_URL"
else
    log_error "✗ Frontend not accessible (HTTP $FRONTEND_CODE)"
fi

# ============================================================
# SUMMARY
# ============================================================

log_step "SUMMARY"

echo "Data Flow Status:"
echo ""
echo "  Wazuh Alerts File:     $([ -f "$ALERTS_FILE" ] && echo "✓ OK" || echo "✗ MISSING")"
echo "  Collector Service:     $(docker ps --filter "name=mini_soc_backend" -q > /dev/null && echo "✓ RUNNING" || echo "✗ STOPPED")"
echo "  Database Events:       $EVENT_COUNT total"
echo "  Recent Activity:       $RECENT_COUNT events (last hour)"
echo "  API Health:            $([ "$HEALTH_CODE" = "200" ] && echo "✓ OK" || echo "✗ FAILED")"
echo "  Redis Pub/Sub:         $(docker-compose -f docker-compose.production.yml exec -T redis redis-cli ping 2>/dev/null | grep -q PONG && echo "✓ OK" || echo "✗ FAILED")"
echo "  Frontend:              $([ "$FRONTEND_CODE" = "200" ] && echo "✓ OK" || echo "✗ FAILED")"
echo ""

if [ "$EVENT_COUNT" -gt 0 ] && [ "$HEALTH_CODE" = "200" ]; then
    log_success "═════════════════════════════════════"
    log_success "✅ DATA FLOW IS WORKING!"
    log_success "═════════════════════════════════════"
    echo ""
    echo "Next steps:"
    echo "1. Login to web UI: $BASE_URL"
    echo "2. Check dashboard for realtime data"
    echo "3. Verify alerts are appearing"
    echo "4. Test WebSocket realtime updates"
    echo ""
else
    log_warn "═════════════════════════════════════"
    log_warn "⚠ DATA FLOW HAS ISSUES"
    log_warn "═════════════════════════════════════"
    echo ""
    echo "Troubleshooting steps:"
    if [ ! -f "$ALERTS_FILE" ]; then
        echo "1. Fix Wazuh alerts file: check Wazuh installation"
    fi
    if [ "$EVENT_COUNT" -eq 0 ]; then
        echo "2. Check collector logs: docker-compose -f docker-compose.production.yml logs backend | grep collector"
    fi
    if [ "$HEALTH_CODE" != "200" ]; then
        echo "3. Check backend health: docker-compose -f docker-compose.production.yml logs backend | tail -50"
    fi
    echo "4. Run debug script: bash debug_deployment.sh"
    echo ""
fi

