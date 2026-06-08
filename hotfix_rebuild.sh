#!/bin/bash

# ============================================================
# Quick Hotfix: Rebuild Backend After Code Changes
# ============================================================
# Usage: bash hotfix_rebuild.sh
# Use this after fixing bugs in backend code
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
log_info "Hotfix: Rebuild Backend Container"
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
log_info "Stopping backend container..."
docker-compose -f docker-compose.production.yml stop backend
log_success "Backend stopped"

echo ""
log_info "Rebuilding backend image (no cache)..."
docker-compose -f docker-compose.production.yml build --no-cache backend
log_success "Backend rebuilt"

echo ""
log_info "Starting backend container..."
docker-compose -f docker-compose.production.yml up -d backend
log_success "Backend started"

echo ""
log_info "Waiting for backend to be ready (15 seconds)..."
sleep 15

echo ""
log_info "Checking backend health..."
if docker-compose -f docker-compose.production.yml exec -T backend curl -sf http://localhost:8000/api/v1/health/ready > /dev/null 2>&1; then
    log_success "✓ Backend is healthy!"
else
    log_error "✗ Backend health check failed!"
    log_info "Showing last 30 lines of logs:"
    docker-compose -f docker-compose.production.yml logs --tail 30 backend
    exit 1
fi

echo ""
log_success "======================================"
log_success "Hotfix Complete!"
log_success "======================================"
echo ""
log_info "Backend container rebuilt and running"
log_info "View logs: docker-compose -f docker-compose.production.yml logs -f backend"
echo ""
