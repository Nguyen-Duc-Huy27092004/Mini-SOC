#!/bin/bash

# ============================================================
# Hotfix: Rebuild Backend + Frontend After Auth Fixes
# ============================================================
# Fixes:
# - Bug #8: Axios interceptor infinite loop
# - Bug #9: /auth/refresh returning 403 instead of 401
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
log_info "Hotfix: Auth Bugs Fixed"
log_info "======================================"
echo ""

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    log_error ".env.production not found! Run deploy script first."
    exit 1
fi

log_info "Loading environment variables..."
set -a
source .env.production
set +a
log_success "Environment loaded"

echo ""

# ============================================================
# 1. STOP SERVICES
# ============================================================

log_info "Stopping backend and frontend..."
docker-compose -f docker-compose.production.yml stop backend frontend
log_success "Services stopped"

echo ""

# ============================================================
# 2. REBUILD BACKEND
# ============================================================

log_info "Rebuilding backend (auth.py fixed)..."
docker-compose -f docker-compose.production.yml build --no-cache backend
log_success "Backend rebuilt"

echo ""

# ============================================================
# 3. REBUILD FRONTEND
# ============================================================

log_info "Rebuilding frontend (interceptor fixed)..."
docker-compose -f docker-compose.production.yml build --no-cache frontend
log_success "Frontend rebuilt"

echo ""

# ============================================================
# 4. START SERVICES
# ============================================================

log_info "Starting services..."
docker-compose -f docker-compose.production.yml up -d backend frontend
log_success "Services started"

echo ""

# ============================================================
# 5. WAIT FOR HEALTH
# ============================================================

log_info "Waiting for backend to be ready (20 seconds)..."
sleep 20

echo ""

# ============================================================
# 6. HEALTH CHECK
# ============================================================

log_info "Checking backend health..."
if docker-compose -f docker-compose.production.yml exec -T backend curl -sf http://localhost:8000/api/v1/health/ready > /dev/null 2>&1; then
    log_success "✓ Backend is healthy!"
else
    log_error "✗ Backend health check failed!"
    log_info "Showing last 30 lines of logs:"
    docker-compose -f docker-compose.production.yml logs --tail 30 backend
    exit 1
fi

NGINX_PORT=${NGINX_PORT:-2709}

log_info "Checking frontend via Nginx..."
if curl -sf http://localhost:$NGINX_PORT > /dev/null 2>&1; then
    log_success "✓ Frontend is accessible!"
else
    log_warn "⚠ Frontend not accessible yet (may need more time)"
fi

echo ""

# ============================================================
# 7. SUMMARY
# ============================================================

log_success "======================================"
log_success "Hotfix Complete!"
log_success "======================================"
echo ""

log_info "Changes applied:"
echo "  ✓ Backend: /auth/refresh now returns 401 (not 403) when CSRF fails"
echo "  ✓ Frontend: Axios interceptor prevents infinite loop"
echo "  ✓ Frontend: Auth errors properly handled"
echo ""

log_info "Test the fixes:"
echo "  1. Open browser: http://localhost:$NGINX_PORT"
echo "  2. Open DevTools → Console"
echo "  3. Refresh page (should see '401 /auth/me' - this is normal!)"
echo "  4. Login → errors should disappear"
echo ""

log_info "Or run automated test:"
echo "  bash test_auth_flow.sh"
echo ""

log_info "View logs:"
echo "  docker-compose -f docker-compose.production.yml logs -f backend"
echo "  docker-compose -f docker-compose.production.yml logs -f frontend"
echo ""
