#!/bin/bash

# ============================================================
# Verify Environment Variables in Docker Containers
# ============================================================
# Usage: bash verify_env.sh
# Check if .env.production variables are loaded in containers
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[⚠]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

echo ""
log_info "Verifying Environment Variables in Containers"
echo "============================================================"
echo ""

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    log_error ".env.production not found in current directory"
    exit 1
fi

log_success ".env.production found"
echo ""

# List all variables from .env.production
log_info "Variables in .env.production:"
echo "---"
grep -v '^#' .env.production | grep '=' | cut -d= -f1 | sort
echo "---"
echo ""

# Check if docker-compose can read the file
log_info "Checking docker-compose configuration..."
if docker-compose -f docker-compose.production.yml config > /dev/null 2>&1; then
    log_success "Docker Compose configuration is valid"
else
    log_error "Docker Compose configuration has errors"
    docker-compose -f docker-compose.production.yml config
    exit 1
fi

echo ""

# Check each service
log_info "Checking services..."
echo ""

# Check Backend
log_info "Backend (mini_soc_backend_prod):"
if docker-compose -f docker-compose.production.yml ps backend | grep -q "Up"; then
    log_success "Container is running"
    
    # Check critical variables
    echo "  Checking environment variables:"
    
    if docker-compose -f docker-compose.production.yml exec -T backend env 2>/dev/null | grep -q "POSTGRES_PASSWORD"; then
        log_success "  ✓ POSTGRES_PASSWORD loaded"
    else
        log_warn "  ✗ POSTGRES_PASSWORD not found"
    fi
    
    if docker-compose -f docker-compose.production.yml exec -T backend env 2>/dev/null | grep -q "REDIS_PASSWORD"; then
        log_success "  ✓ REDIS_PASSWORD loaded"
    else
        log_warn "  ✗ REDIS_PASSWORD not found"
    fi
    
    if docker-compose -f docker-compose.production.yml exec -T backend env 2>/dev/null | grep -q "SECRET_KEY"; then
        log_success "  ✓ SECRET_KEY loaded"
    else
        log_warn "  ✗ SECRET_KEY not found"
    fi
    
    if docker-compose -f docker-compose.production.yml exec -T backend env 2>/dev/null | grep -q "WAZUH_API_URL"; then
        log_success "  ✓ WAZUH_API_URL loaded"
    else
        log_warn "  ✗ WAZUH_API_URL not found"
    fi
else
    log_warn "Container is not running"
fi

echo ""

# Check Database
log_info "Database (mini_soc_db_prod):"
if docker-compose -f docker-compose.production.yml ps db | grep -q "Up"; then
    log_success "Container is running"
    
    if docker-compose -f docker-compose.production.yml exec -T db env 2>/dev/null | grep -q "POSTGRES_PASSWORD"; then
        log_success "  ✓ POSTGRES_PASSWORD loaded"
    else
        log_warn "  ✗ POSTGRES_PASSWORD not found"
    fi
else
    log_warn "Container is not running"
fi

echo ""

# Check Redis
log_info "Redis (mini_soc_redis_prod):"
if docker-compose -f docker-compose.production.yml ps redis | grep -q "Up"; then
    log_success "Container is running"
    
    if docker-compose -f docker-compose.production.yml exec -T redis env 2>/dev/null | grep -q "REDIS_PASSWORD"; then
        log_success "  ✓ REDIS_PASSWORD loaded"
    else
        log_warn "  ✗ REDIS_PASSWORD not found"
    fi
else
    log_warn "Container is not running"
fi

echo ""

# Health checks
log_info "Health Checks:"
echo ""

if curl -s http://localhost:8000/api/v1/health/ready > /dev/null 2>&1; then
    log_success "Backend is responding"
else
    log_warn "Backend not responding (may still be starting)"
fi

if curl -s http://localhost > /dev/null 2>&1; then
    log_success "Frontend is responding"
else
    log_warn "Frontend not responding (may still be starting)"
fi

echo ""
echo "============================================================"
log_info "Verification complete"
echo "============================================================"
echo ""
echo "If variables are not loaded:"
echo "1. Check .env.production file format (no spaces around =)"
echo "2. Restart containers: docker-compose -f docker-compose.production.yml restart"
echo "3. Check logs: docker-compose -f docker-compose.production.yml logs backend"
echo ""
