#!/bin/bash

# ============================================================
# Auto-Fix Authentication & WebSocket Issues
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
log_info "Auto-Fix Auth & WebSocket Issues"
log_info "======================================"
echo ""

# Check .env.production exists
if [ ! -f ".env.production" ]; then
    log_error ".env.production not found!"
    exit 1
fi

# Backup
cp .env.production .env.production.backup.$(date +%s)
log_success "Backed up .env.production"

# Get current values
NGINX_PORT=$(grep "^NGINX_PORT=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "2709")
SERVER_IP=$(grep "^SERVER_IP=" .env.production | cut -d'=' -f2 | tr -d '"' || hostname -I | awk '{print $1}')

log_info "Detected Server IP: $SERVER_IP"
log_info "Detected Nginx Port: $NGINX_PORT"
echo ""

# ============================================================
# FIX #1: WebSocket URL
# ============================================================

log_info "Fix #1: Correcting WebSocket URL..."

CURRENT_WS=$(grep "^VITE_WS_URL=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "")

if echo "$CURRENT_WS" | grep -q "/ws/ws"; then
    log_warn "Found double /ws/ws in WebSocket URL"
    NEW_WS_URL="ws://$SERVER_IP:$NGINX_PORT/ws"
    
    sed -i.bak "s|^VITE_WS_URL=.*|VITE_WS_URL=\"$NEW_WS_URL\"|" .env.production
    log_success "Fixed: VITE_WS_URL=\"$NEW_WS_URL\""
elif [ -z "$CURRENT_WS" ]; then
    log_warn "VITE_WS_URL not found, adding..."
    NEW_WS_URL="ws://$SERVER_IP:$NGINX_PORT/ws"
    echo "VITE_WS_URL=\"$NEW_WS_URL\"" >> .env.production
    log_success "Added: VITE_WS_URL=\"$NEW_WS_URL\""
else
    log_success "VITE_WS_URL looks correct: $CURRENT_WS"
fi

# ============================================================
# FIX #2: CORS Origins
# ============================================================

log_info "Fix #2: Ensuring CORS origins are correct..."

CURRENT_CORS=$(grep "^BACKEND_CORS_ORIGINS=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "")

if [ -z "$CURRENT_CORS" ]; then
    log_warn "BACKEND_CORS_ORIGINS is empty!"
    NEW_CORS="http://$SERVER_IP:$NGINX_PORT,http://localhost:$NGINX_PORT,http://127.0.0.1:$NGINX_PORT"
    sed -i "s|^BACKEND_CORS_ORIGINS=.*|BACKEND_CORS_ORIGINS=\"$NEW_CORS\"|" .env.production
    log_success "Set: BACKEND_CORS_ORIGINS=\"$NEW_CORS\""
elif ! echo "$CURRENT_CORS" | grep -q "$SERVER_IP"; then
    log_warn "BACKEND_CORS_ORIGINS missing server IP"
    NEW_CORS="http://$SERVER_IP:$NGINX_PORT,http://localhost:$NGINX_PORT,$CURRENT_CORS"
    sed -i "s|^BACKEND_CORS_ORIGINS=.*|BACKEND_CORS_ORIGINS=\"$NEW_CORS\"|" .env.production
    log_success "Updated: BACKEND_CORS_ORIGINS=\"$NEW_CORS\""
else
    log_success "BACKEND_CORS_ORIGINS looks correct"
fi

# ============================================================
# FIX #3: Cookie Settings
# ============================================================

log_info "Fix #3: Checking cookie settings for HTTP..."

# Check if using HTTPS
if echo "$SERVER_IP" | grep -qE "^(localhost|127\.0\.0\.1)$" || [ "$NGINX_PORT" != "443" ]; then
    # HTTP mode
    COOKIE_SECURE=$(grep "^COOKIE_SECURE=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "")
    
    if [ "$COOKIE_SECURE" = "true" ]; then
        log_warn "COOKIE_SECURE=true but using HTTP, changing to false..."
        sed -i 's/^COOKIE_SECURE=.*/COOKIE_SECURE="false"/' .env.production
        log_success "Set: COOKIE_SECURE=\"false\""
    else
        log_success "COOKIE_SECURE already false (correct for HTTP)"
    fi
    
    # Cookie domain should be empty for same-origin
    COOKIE_DOMAIN=$(grep "^COOKIE_DOMAIN=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "")
    if [ -n "$COOKIE_DOMAIN" ]; then
        log_warn "COOKIE_DOMAIN is set, clearing for same-origin..."
        sed -i 's/^COOKIE_DOMAIN=.*/COOKIE_DOMAIN=""/' .env.production
        log_success "Cleared COOKIE_DOMAIN (same-origin mode)"
    fi
fi

# ============================================================
# FIX #4: CSRF Validation
# ============================================================

log_info "Fix #4: Checking CSRF settings..."

CSRF_VALIDATE_ORIGIN=$(grep "^CSRF_VALIDATE_ORIGIN=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "")

if [ "$CSRF_VALIDATE_ORIGIN" != "false" ]; then
    log_warn "Setting CSRF_VALIDATE_ORIGIN=false for development..."
    sed -i 's/^CSRF_VALIDATE_ORIGIN=.*/CSRF_VALIDATE_ORIGIN="false"/' .env.production
    log_success "Set: CSRF_VALIDATE_ORIGIN=\"false\""
else
    log_success "CSRF_VALIDATE_ORIGIN already false"
fi

# ============================================================
# FIX #5: Frontend URL
# ============================================================

log_info "Fix #5: Ensuring frontend URL is correct..."

FRONTEND_URL=$(grep "^FRONTEND_URL=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "")
VITE_API_URL=$(grep "^VITE_API_URL=" .env.production | cut -d'=' -f2 | tr -d '"' || echo "")

CORRECT_FRONTEND="http://$SERVER_IP:$NGINX_PORT"
CORRECT_API="http://$SERVER_IP:$NGINX_PORT/api/v1"

if [ "$FRONTEND_URL" != "$CORRECT_FRONTEND" ]; then
    sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=\"$CORRECT_FRONTEND\"|" .env.production
    log_success "Updated: FRONTEND_URL=\"$CORRECT_FRONTEND\""
fi

if [ "$VITE_API_URL" != "$CORRECT_API" ]; then
    sed -i "s|^VITE_API_URL=.*|VITE_API_URL=\"$CORRECT_API\"|" .env.production
    log_success "Updated: VITE_API_URL=\"$CORRECT_API\""
fi

echo ""
log_success "======================================"
log_success "Configuration Fixed!"
log_success "======================================"
echo ""

# Show what changed
log_info "Summary of changes:"
echo ""
echo "  Server:           http://$SERVER_IP:$NGINX_PORT"
echo "  API:              http://$SERVER_IP:$NGINX_PORT/api/v1"
echo "  WebSocket:        ws://$SERVER_IP:$NGINX_PORT/ws"
echo "  CORS Origins:     $(grep "^BACKEND_CORS_ORIGINS=" .env.production | cut -d'=' -f2)"
echo "  Cookie Secure:    $(grep "^COOKIE_SECURE=" .env.production | cut -d'=' -f2)"
echo "  CSRF Validate:    $(grep "^CSRF_VALIDATE_ORIGIN=" .env.production | cut -d'=' -f2)"
echo ""

log_info "Next steps:"
echo ""
echo "1. Rebuild and restart containers:"
echo "   docker-compose -f docker-compose.production.yml build frontend backend"
echo "   docker-compose -f docker-compose.production.yml up -d"
echo ""
echo "2. Wait 30 seconds for services to start"
echo ""
echo "3. Test in browser: http://$SERVER_IP:$NGINX_PORT"
echo ""
echo "4. Check browser console for errors"
echo ""
echo "5. If still issues, run:"
echo "   bash diagnose_auth_issues.sh"
echo ""

log_warn "⚠️  Important: You MUST rebuild frontend for WebSocket URL changes!"
echo ""

read -p "Rebuild frontend now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "Rebuilding frontend..."
    docker-compose -f docker-compose.production.yml build --no-cache frontend
    log_success "Frontend rebuilt"
    
    log_info "Restarting containers..."
    docker-compose -f docker-compose.production.yml restart backend frontend nginx
    log_success "Containers restarted"
    
    echo ""
    log_success "✅ Ready! Access at: http://$SERVER_IP:$NGINX_PORT"
else
    log_warn "Skipped rebuild. Remember to rebuild frontend manually!"
fi

echo ""
