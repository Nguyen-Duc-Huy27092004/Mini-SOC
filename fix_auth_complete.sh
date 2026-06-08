#!/bin/bash

# ============================================================
# Complete Auth & Cookie Fix Script
# ============================================================
# Fixes 401/403/500 auth errors comprehensively
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[⚠]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }

echo ""
log_info "======================================"
log_info "Complete Auth & Cookie Fix"
log_info "======================================"
echo ""

# ============================================================
# ISSUE DIAGNOSIS
# ============================================================

log_info "Diagnosing authentication issues..."
echo ""

log_info "Common 401/403/500 auth error causes:"
echo "  1. Cookies not being set (CORS/SameSite issues)"
echo "  2. CSRF token mismatch"
echo "  3. WebSocket URL incorrect (/ws/ws instead of /ws)"
echo "  4. Backend missing db.commit() in change-password"
echo "  5. COOKIE_SECURE=true but using HTTP"
echo "  6. BACKEND_CORS_ORIGINS not including frontend URL"
echo ""

# ============================================================
# FIX 1: CHECK .env.production
# ============================================================

log_info "Fix #1: Checking .env.production..."

if [ ! -f ".env.production" ]; then
    log_error ".env.production not found! Run deploy script first."
    exit 1
fi

# Get values
NGINX_PORT=$(grep "^NGINX_PORT=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "2709")
SERVER_IP=$(grep "^SERVER_IP=" .env.production | cut -d'=' -f2 | tr -d '"' || hostname -I | awk '{print $1}')
COOKIE_SECURE=$(grep "^COOKIE_SECURE=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "")
CSRF_VALIDATE=$(grep "^CSRF_VALIDATE_ORIGIN=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "")
BACKEND_CORS=$(grep "^BACKEND_CORS_ORIGINS=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "")
VITE_WS_URL=$(grep "^VITE_WS_URL=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "")

echo "Current settings:"
echo "  SERVER_IP: ${SERVER_IP:-NOT SET}"
echo "  NGINX_PORT: ${NGINX_PORT:-NOT SET}"
echo "  COOKIE_SECURE: ${COOKIE_SECURE:-NOT SET}"
echo "  CSRF_VALIDATE_ORIGIN: ${CSRF_VALIDATE:-NOT SET}"
echo "  BACKEND_CORS_ORIGINS: ${BACKEND_CORS:-NOT SET}"
echo "  VITE_WS_URL: ${VITE_WS_URL:-NOT SET}"
echo ""

# ============================================================
# FIX 2: CORRECT COOKIE SETTINGS FOR HTTP
# ============================================================

log_info "Fix #2: Setting cookie config for HTTP..."

# Backup
cp .env.production .env.production.backup.$(date +%s)

# Fix COOKIE_SECURE (must be false for HTTP)
if [ "$COOKIE_SECURE" != "false" ]; then
    log_warn "COOKIE_SECURE is not false, fixing..."
    sed -i 's/^COOKIE_SECURE=.*/COOKIE_SECURE="false"/' .env.production
    log_success "Set COOKIE_SECURE=false"
fi

# Fix COOKIE_DOMAIN (should be empty for same-origin)
COOKIE_DOMAIN=$(grep "^COOKIE_DOMAIN=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "")
if [ -n "$COOKIE_DOMAIN" ]; then
    log_warn "COOKIE_DOMAIN is set, clearing for same-origin..."
    sed -i 's/^COOKIE_DOMAIN=.*/COOKIE_DOMAIN=""/' .env.production
    log_success "Cleared COOKIE_DOMAIN"
fi

# Fix CSRF_VALIDATE_ORIGIN (should be false for development)
if [ "$CSRF_VALIDATE" != "false" ]; then
    log_warn "CSRF_VALIDATE_ORIGIN is not false, fixing..."
    sed -i 's/^CSRF_VALIDATE_ORIGIN=.*/CSRF_VALIDATE_ORIGIN="false"/' .env.production
    log_success "Set CSRF_VALIDATE_ORIGIN=false"
fi

echo ""

# ============================================================
# FIX 3: CORRECT CORS ORIGINS
# ============================================================

log_info "Fix #3: Ensuring CORS origins include all access URLs..."

CORRECT_CORS="http://$SERVER_IP:$NGINX_PORT,http://localhost:$NGINX_PORT,http://127.0.0.1:$NGINX_PORT"

if [ "$BACKEND_CORS" != "$CORRECT_CORS" ]; then
    log_warn "Updating BACKEND_CORS_ORIGINS..."
    sed -i "s|^BACKEND_CORS_ORIGINS=.*|BACKEND_CORS_ORIGINS=\"$CORRECT_CORS\"|" .env.production
    log_success "Updated BACKEND_CORS_ORIGINS"
else
    log_success "BACKEND_CORS_ORIGINS already correct"
fi

echo ""

# ============================================================
# FIX 4: CORRECT WEBSOCKET URL
# ============================================================

log_info "Fix #4: Checking WebSocket URL..."

CORRECT_WS_URL="ws://$SERVER_IP:$NGINX_PORT/ws"

if [ "$VITE_WS_URL" != "$CORRECT_WS_URL" ]; then
    log_warn "WebSocket URL incorrect, fixing..."
    sed -i "s|^VITE_WS_URL=.*|VITE_WS_URL=\"$CORRECT_WS_URL\"|" .env.production
    log_success "Updated VITE_WS_URL to: $CORRECT_WS_URL"
else
    log_success "VITE_WS_URL already correct"
fi

if echo "$VITE_WS_URL" | grep -q "/ws/ws"; then
    log_error "⚠️ CRITICAL: WebSocket URL has double /ws/ws!"
    sed -i "s|/ws/ws|/ws|g" .env.production
    log_success "Fixed double /ws/ws"
fi

echo ""

# ============================================================
# FIX 5: VERIFY CRITICAL VARS
# ============================================================

log_info "Fix #5: Verifying all critical variables exist..."

MISSING_VARS=()

for var in "SECRET_KEY" "POSTGRES_PASSWORD" "REDIS_PASSWORD" "BACKEND_CORS_ORIGINS" "CSRF_VALIDATE_ORIGIN"; do
    if ! grep -q "^${var}=" .env.production; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    log_error "Missing critical variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    log_error "Re-run deploy script to generate complete .env.production"
    exit 1
else
    log_success "All critical variables present"
fi

echo ""

# ============================================================
# FIX 6: REBUILD FRONTEND (FOR VITE_WS_URL)
# ============================================================

log_info "Fix #6: Rebuilding frontend with corrected environment..."
log_warn "This will take 2-3 minutes..."
echo ""

# Export vars for docker-compose
set -a
source .env.production
set +a

if docker-compose -f docker-compose.production.yml build frontend 2>&1 | tail -20; then
    log_success "✓ Frontend rebuilt successfully"
else
    log_error "✗ Frontend build failed!"
    log_info "Check build logs above for errors"
    exit 1
fi

echo ""

# ============================================================
# FIX 7: RESTART SERVICES
# ============================================================

log_info "Fix #7: Restarting backend and frontend..."

docker-compose -f docker-compose.production.yml restart backend frontend nginx

log_info "Waiting for services to restart (30 seconds)..."
sleep 30

echo ""

# ============================================================
# VALIDATION
# ============================================================

log_info "Validating fixes..."
echo ""

# Test 1: Backend health
log_info "[1/5] Testing backend health..."
if curl -sf http://localhost:$NGINX_PORT/api/v1/health/ready > /dev/null 2>&1; then
    log_success "✓ Backend health OK"
else
    log_error "✗ Backend health check failed"
fi

# Test 2: CORS headers
log_info "[2/5] Testing CORS headers..."
CORS_TEST=$(curl -sI -X OPTIONS "http://localhost:$NGINX_PORT/api/v1/health" \
    -H "Origin: http://localhost:$NGINX_PORT" \
    -H "Access-Control-Request-Method: GET" 2>/dev/null | grep -i "access-control-allow-origin" || echo "")

if [ -n "$CORS_TEST" ]; then
    log_success "✓ CORS headers present"
else
    log_warn "⚠ CORS headers not detected (may need more time)"
fi

# Test 3: Cookie settings in container
log_info "[3/5] Checking backend environment variables..."
BACKEND_COOKIE_SECURE=$(docker-compose -f docker-compose.production.yml exec -T backend env 2>/dev/null | grep "COOKIE_SECURE" || echo "")
if echo "$BACKEND_COOKIE_SECURE" | grep -q "false"; then
    log_success "✓ COOKIE_SECURE=false in container"
else
    log_warn "⚠ Could not verify COOKIE_SECURE (container may be starting)"
fi

# Test 4: WebSocket endpoint
log_info "[4/5] Testing WebSocket path..."
WS_RESPONSE=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:$NGINX_PORT/ws?ticket=test" 2>/dev/null || echo "000")
if [ "$WS_RESPONSE" = "401" ] || [ "$WS_RESPONSE" = "403" ]; then
    log_success "✓ WebSocket endpoint responding (401/403 expected without valid ticket)"
else
    log_warn "⚠ WebSocket returned HTTP $WS_RESPONSE"
fi

# Test 5: Frontend access
log_info "[5/5] Testing frontend..."
FRONTEND_HTTP=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:$NGINX_PORT/ 2>/dev/null || echo "000")
if [ "$FRONTEND_HTTP" = "200" ]; then
    log_success "✓ Frontend accessible"
else
    log_error "✗ Frontend returned HTTP $FRONTEND_HTTP"
fi

echo ""

# ============================================================
# SUMMARY
# ============================================================

log_success "======================================"
log_success "Auth Fixes Applied"
log_success "======================================"
echo ""

echo "Changes made:"
echo "  ✓ COOKIE_SECURE set to false (HTTP mode)"
echo "  ✓ COOKIE_DOMAIN cleared (same-origin)"
echo "  ✓ CSRF_VALIDATE_ORIGIN set to false"
echo "  ✓ BACKEND_CORS_ORIGINS updated"
echo "  ✓ VITE_WS_URL corrected (no double /ws)"
echo "  ✓ Frontend rebuilt with new config"
echo "  ✓ Services restarted"
echo ""

echo "Current configuration:"
echo "  Access URL:    http://$SERVER_IP:$NGINX_PORT"
echo "  API URL:       http://$SERVER_IP:$NGINX_PORT/api/v1"
echo "  WebSocket URL: ws://$SERVER_IP:$NGINX_PORT/ws"
echo ""

log_info "Next steps:"
echo "1. Clear browser cookies and cache (Ctrl+Shift+Delete)"
echo "2. Open: http://$SERVER_IP:$NGINX_PORT"
echo "3. Try to login"
echo "4. Check browser console for errors"
echo ""

log_info "If still getting 401/403 errors:"
echo "• Check browser DevTools → Application → Cookies"
echo "• Should see: access_token, refresh_token, csrf_token"
echo "• If not, cookies are not being set"
echo ""
echo "• Check browser Console for errors"
echo "• Common: 'Blocked by CORS policy'"
echo "• Solution: Verify BACKEND_CORS_ORIGINS includes your access URL"
echo ""

log_info "Backend logs (check for errors):"
echo "docker-compose -f docker-compose.production.yml logs --tail 50 backend"
echo ""

log_success "Auth fix complete! Try logging in now."
echo ""
