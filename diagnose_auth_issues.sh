#!/bin/bash

# ============================================================
# Diagnose Authentication & WebSocket Issues
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_section() { echo -e "\n${GREEN}═══ $1 ═══${NC}\n"; }

echo ""
log_section "Authentication & WebSocket Diagnostics"

# ============================================================
# 1. CHECK ENVIRONMENT VARIABLES
# ============================================================

log_section "1. Environment Variables"

if [ ! -f ".env.production" ]; then
    log_error ".env.production not found!"
    exit 1
fi

log_info "Checking critical variables..."
echo ""

# Cookie settings
COOKIE_SECURE=$(grep "^COOKIE_SECURE=" .env.production | cut -d'=' -f2 | tr -d '"')
COOKIE_DOMAIN=$(grep "^COOKIE_DOMAIN=" .env.production | cut -d'=' -f2 | tr -d '"')
CSRF_VALIDATE_ORIGIN=$(grep "^CSRF_VALIDATE_ORIGIN=" .env.production | cut -d'=' -f2 | tr -d '"')
BACKEND_CORS_ORIGINS=$(grep "^BACKEND_CORS_ORIGINS=" .env.production | cut -d'=' -f2 | tr -d '"')
VITE_WS_URL=$(grep "^VITE_WS_URL=" .env.production | cut -d'=' -f2 | tr -d '"')
NGINX_PORT=$(grep "^NGINX_PORT=" .env.production | cut -d'=' -f2 | tr -d '"')

echo "COOKIE_SECURE: ${COOKIE_SECURE:-NOT SET}"
echo "COOKIE_DOMAIN: ${COOKIE_DOMAIN:-NOT SET (empty is OK for same-origin)}"
echo "CSRF_VALIDATE_ORIGIN: ${CSRF_VALIDATE_ORIGIN:-NOT SET}"
echo "BACKEND_CORS_ORIGINS: ${BACKEND_CORS_ORIGINS:-NOT SET}"
echo "VITE_WS_URL: ${VITE_WS_URL:-NOT SET}"
echo "NGINX_PORT: ${NGINX_PORT:-2709}"

echo ""

# Validate settings
if [ "$COOKIE_SECURE" = "true" ] && ! echo "$VITE_WS_URL" | grep -q "wss://"; then
    log_error "⚠️  COOKIE_SECURE=true but VITE_WS_URL uses ws:// (should be wss://)"
fi

if [ -z "$BACKEND_CORS_ORIGINS" ]; then
    log_error "⚠️  BACKEND_CORS_ORIGINS is empty! Frontend requests will be blocked."
fi

# ============================================================
# 2. TEST BACKEND API
# ============================================================

log_section "2. Backend API Tests"

PORT="${NGINX_PORT:-2709}"
BASE_URL="http://localhost:$PORT"

log_info "Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/api/v1/health/ready" 2>/dev/null)
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | grep "HTTP_CODE" | cut -d':' -f2)

if [ "$HTTP_CODE" = "200" ]; then
    log_success "Health check OK (200)"
else
    log_error "Health check FAILED (${HTTP_CODE:-no response})"
fi

echo ""
log_info "Testing login endpoint..."
LOGIN_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"test"}' \
    -c /tmp/cookies.txt \
    2>/dev/null)

LOGIN_CODE=$(echo "$LOGIN_RESPONSE" | grep "HTTP_CODE" | cut -d':' -f2)
echo "Login response code: $LOGIN_CODE"

if [ "$LOGIN_CODE" = "401" ]; then
    log_success "Login endpoint responding (401 = correct for wrong credentials)"
elif [ "$LOGIN_CODE" = "429" ]; then
    log_error "⚠️  Rate limited! Wait 60 seconds or check rate limit settings"
else
    log_error "Unexpected response: $LOGIN_CODE"
    echo "$LOGIN_RESPONSE" | grep -v "HTTP_CODE"
fi

echo ""
log_info "Checking cookies set by backend..."
if [ -f "/tmp/cookies.txt" ]; then
    cat /tmp/cookies.txt | grep -E "access_token|refresh_token|csrf_token" || echo "  No auth cookies found"
else
    echo "  No cookies file"
fi

# ============================================================
# 3. TEST WEBSOCKET
# ============================================================

log_section "3. WebSocket Configuration"

log_info "Backend WebSocket route: /ws"
log_info "Frontend should connect to: ws://<server>:$PORT/ws?ticket=<token>"
log_info "Current VITE_WS_URL: ${VITE_WS_URL:-NOT SET}"

echo ""
if echo "$VITE_WS_URL" | grep -q "/ws/ws"; then
    log_error "⚠️  CRITICAL: VITE_WS_URL has /ws/ws (double ws)"
    log_error "    Should be: ws://<server>:$PORT/ws"
    log_error "    Current:   $VITE_WS_URL"
fi

# ============================================================
# 4. CHECK BACKEND CONTAINER LOGS
# ============================================================

log_section "4. Recent Backend Errors"

log_info "Last 20 error/warning lines from backend:"
echo ""
docker-compose -f docker-compose.production.yml logs --tail 100 backend 2>/dev/null | \
    grep -iE "error|warning|exception|failed|traceback" | tail -20 || \
    echo "  No errors found in recent logs"

# ============================================================
# 5. CHECK CORS HEADERS
# ============================================================

log_section "5. CORS Headers Check"

log_info "Testing CORS preflight..."
CORS_RESPONSE=$(curl -s -i -X OPTIONS "$BASE_URL/api/v1/health" \
    -H "Origin: http://localhost:$PORT" \
    -H "Access-Control-Request-Method: GET" \
    2>/dev/null | head -20)

if echo "$CORS_RESPONSE" | grep -qi "Access-Control-Allow-Origin"; then
    log_success "CORS headers present"
    echo "$CORS_RESPONSE" | grep -i "Access-Control"
else
    log_error "CORS headers missing!"
    echo "$CORS_RESPONSE"
fi

# ============================================================
# 6. RECOMMENDATIONS
# ============================================================

log_section "Recommendations"

echo "Based on the errors you provided:"
echo ""
echo "1. 401/403 Errors:"
echo "   - Check BACKEND_CORS_ORIGINS includes your frontend URL"
echo "   - Ensure COOKIE_SECURE=false for HTTP (or use HTTPS)"
echo "   - Verify cookies are being set (check browser DevTools → Application → Cookies)"
echo ""
echo "2. WebSocket Failed:"
echo "   - Fix VITE_WS_URL if it has /ws/ws"
echo "   - Should be: ws://192.168.10.4:$PORT/ws"
echo "   - Rebuild frontend: docker-compose -f docker-compose.production.yml build frontend"
echo ""
echo "3. No Data:"
echo "   - Check Wazuh alerts file exists: /var/ossec/logs/alerts/alerts.json"
echo "   - Verify Wazuh API credentials in .env.production"
echo "   - Check collector logs: docker-compose -f docker-compose.production.yml logs collector"
echo ""

log_section "Quick Fixes"

echo "Fix #1: CORS Origins"
echo '  sed -i "s|^BACKEND_CORS_ORIGINS=.*|BACKEND_CORS_ORIGINS=\"http://192.168.10.4:'$PORT',http://localhost:'$PORT'\"|" .env.production'
echo ""
echo "Fix #2: WebSocket URL"
echo '  sed -i "s|^VITE_WS_URL=.*|VITE_WS_URL=\"ws://192.168.10.4:'$PORT'/ws\"|" .env.production'
echo ""
echo "Fix #3: Cookie Settings (for HTTP)"
echo '  sed -i "s|^COOKIE_SECURE=.*|COOKIE_SECURE=\"false\"|" .env.production'
echo ""
echo "After fixes, rebuild:"
echo "  docker-compose -f docker-compose.production.yml build frontend"
echo "  docker-compose -f docker-compose.production.yml restart backend frontend"
echo ""
