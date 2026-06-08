#!/bin/bash

# ============================================================
# Mini-SOC Deployment Validation Script
# ============================================================
# Usage: bash validate_deployment.sh
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
log_info "Mini-SOC Deployment Validation"
log_info "======================================"
echo ""

# ============================================================
# 1. CHECK .env.production
# ============================================================

log_info "1. Checking .env.production file..."

if [ ! -f ".env.production" ]; then
    log_error ".env.production not found!"
    exit 1
fi

# Check critical variables
MISSING_VARS=()
for var in "SECRET_KEY" "POSTGRES_PASSWORD" "REDIS_PASSWORD" "WAZUH_API_URL" "CSRF_VALIDATE_ORIGIN"; do
    if ! grep -q "^${var}=" .env.production; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    log_error "Missing variables in .env.production:"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    exit 1
fi

log_success ".env.production is valid"
echo ""

# ============================================================
# 2. CHECK DOCKER CONTAINERS
# ============================================================

log_info "2. Checking Docker containers..."

REQUIRED_CONTAINERS=("mini_soc_db_prod" "mini_soc_redis_prod" "mini_soc_backend_prod" "mini_soc_nginx_prod")
FAILED_CONTAINERS=()

for container in "${REQUIRED_CONTAINERS[@]}"; do
    if docker ps --filter "name=$container" --filter "status=running" | grep -q "$container"; then
        log_success "$container is running"
    else
        log_error "$container is not running!"
        FAILED_CONTAINERS+=("$container")
    fi
done

if [ ${#FAILED_CONTAINERS[@]} -ne 0 ]; then
    log_error "Some containers are not running. Check logs:"
    for container in "${FAILED_CONTAINERS[@]}"; do
        echo "  docker logs $container"
    done
    exit 1
fi

echo ""

# ============================================================
# 3. CHECK DATABASE CONNECTION
# ============================================================

log_info "3. Checking database connection..."

if docker-compose -f docker-compose.production.yml exec -T db pg_isready -U postgres > /dev/null 2>&1; then
    log_success "PostgreSQL is ready"
else
    log_error "PostgreSQL is not ready!"
    exit 1
fi

# Check if migrations ran
MIGRATION_CHECK=$(docker-compose -f docker-compose.production.yml exec -T db psql -U postgres -d mini_soc_prod -tAc "SELECT COUNT(*) FROM alembic_version" 2>/dev/null || echo "0")
if [ "$MIGRATION_CHECK" -gt 0 ]; then
    log_success "Database migrations applied (version count: $MIGRATION_CHECK)"
else
    log_warn "No migrations found in database!"
fi

echo ""

# ============================================================
# 4. CHECK REDIS CONNECTION
# ============================================================

log_info "4. Checking Redis connection..."

REDIS_PASSWORD=$(grep "REDIS_PASSWORD=" .env.production | cut -d'=' -f2 | tr -d '"')
if docker-compose -f docker-compose.production.yml exec -T redis redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q "PONG"; then
    log_success "Redis is ready"
else
    log_error "Redis connection failed!"
    exit 1
fi

echo ""

# ============================================================
# 5. CHECK BACKEND ENVIRONMENT VARIABLES
# ============================================================

log_info "5. Checking backend environment variables..."

BACKEND_VARS=("SECRET_KEY" "POSTGRES_PASSWORD" "REDIS_PASSWORD" "CSRF_VALIDATE_ORIGIN" "BACKEND_CORS_ORIGINS")
BACKEND_MISSING=()

for var in "${BACKEND_VARS[@]}"; do
    if ! docker-compose -f docker-compose.production.yml exec -T backend env 2>/dev/null | grep -q "^${var}="; then
        BACKEND_MISSING+=("$var")
    fi
done

if [ ${#BACKEND_MISSING[@]} -ne 0 ]; then
    log_error "Missing environment variables in backend container:"
    for var in "${BACKEND_MISSING[@]}"; do
        echo "  - $var"
    done
    log_warn "Backend may crash on startup!"
else
    log_success "All required environment variables present in backend"
fi

echo ""

# ============================================================
# 6. CHECK BACKEND HEALTH
# ============================================================

log_info "6. Checking backend health endpoint..."

NGINX_PORT=$(grep "NGINX_PORT=" .env.production | cut -d'=' -f2 | tr -d '"')
NGINX_PORT=${NGINX_PORT:-2709}

# Try internal backend first
if docker-compose -f docker-compose.production.yml exec -T backend curl -sf http://localhost:8000/api/v1/health/ready > /dev/null 2>&1; then
    log_success "Backend internal health check passed"
else
    log_error "Backend internal health check failed!"
    log_info "Checking backend logs:"
    docker-compose -f docker-compose.production.yml logs --tail=20 backend
    exit 1
fi

# Try via Nginx
if curl -sf http://localhost:$NGINX_PORT/api/v1/health/ready > /dev/null 2>&1; then
    log_success "Backend accessible via Nginx (port $NGINX_PORT)"
else
    log_warn "Backend not accessible via Nginx yet (may need more time)"
fi

echo ""

# ============================================================
# 7. CHECK WAZUH INTEGRATION
# ============================================================

log_info "7. Checking Wazuh integration..."

WAZUH_API_URL=$(grep "WAZUH_API_URL=" .env.production | cut -d'=' -f2 | tr -d '"')
if [ -n "$WAZUH_API_URL" ]; then
    log_success "Wazuh API URL configured: $WAZUH_API_URL"
    
    # Check if alerts file is mounted
    if docker-compose -f docker-compose.production.yml exec -T backend test -f /var/ossec/logs/alerts/alerts.json 2>/dev/null; then
        log_success "Wazuh alerts file is mounted"
    else
        log_warn "Wazuh alerts file not found (will use API instead)"
    fi
else
    log_error "Wazuh API URL not configured!"
fi

echo ""

# ============================================================
# 8. SUMMARY
# ============================================================

log_success "======================================"
log_success "Validation Complete!"
log_success "======================================"
echo ""
log_info "Access URLs:"
echo "  - Web UI:         http://localhost:$NGINX_PORT"
echo "  - API Health:     http://localhost:$NGINX_PORT/api/v1/health/ready"
echo "  - API Docs:       http://localhost:$NGINX_PORT/api/v1/docs (if DEBUG=true)"
echo ""
log_info "Container logs:"
echo "  - Backend:  docker-compose -f docker-compose.production.yml logs -f backend"
echo "  - Frontend: docker-compose -f docker-compose.production.yml logs -f frontend"
echo "  - Nginx:    docker-compose -f docker-compose.production.yml logs -f nginx"
echo "  - Database: docker-compose -f docker-compose.production.yml logs -f db"
echo ""
log_success "System is ready for use!"
echo ""
