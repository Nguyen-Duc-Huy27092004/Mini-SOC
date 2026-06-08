#!/bin/bash

# ============================================================
# Mini-SOC Deployment Debug Script
# ============================================================
# Run this when deployment fails to diagnose issues
# Usage: bash debug_deployment.sh
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[DEBUG]${NC} $1"; }
log_section() { echo -e "\n${GREEN}$1${NC}\n"; }

echo ""
log_section "=========================================="
log_section "Mini-SOC Deployment Debug"
log_section "=========================================="

# ============================================================
# 1. CONTAINER STATUS
# ============================================================

log_section "1. Container Status"
docker-compose -f docker-compose.production.yml ps
echo ""

# ============================================================
# 2. FAILED CONTAINERS LOGS
# ============================================================

log_section "2. Checking for failed/exited containers..."

EXITED=$(docker ps -a --filter "status=exited" --filter "name=mini_soc" --format "{{.Names}}")
if [ -n "$EXITED" ]; then
    log_error "Found exited containers:"
    echo "$EXITED"
    echo ""
    
    for container in $EXITED; do
        log_error "Logs for $container (last 50 lines):"
        docker logs --tail 50 "$container"
        echo ""
    done
else
    log_info "No exited containers found"
fi

echo ""

# ============================================================
# 3. ENVIRONMENT VARIABLES
# ============================================================

log_section "3. Environment Variables Check"

if [ -f ".env.production" ]; then
    log_info "Checking .env.production content (secrets hidden)..."
    
    # Check if critical vars are empty
    while IFS= read -r line; do
        if [[ "$line" =~ ^([A-Z_]+)=\"?\"?$ ]]; then
            var_name="${BASH_REMATCH[1]}"
            log_error "Empty variable: $var_name"
        fi
    done < .env.production
    
    log_info ""
    log_info "Critical variables status:"
    for var in "SECRET_KEY" "POSTGRES_PASSWORD" "REDIS_PASSWORD" "WAZUH_API_URL"; do
        if grep -q "^${var}=.\+" .env.production; then
            echo "  ✓ $var is set"
        else
            log_error "  ✗ $var is MISSING or EMPTY!"
        fi
    done
else
    log_error ".env.production not found!"
fi

echo ""

# ============================================================
# 4. DATABASE CONNECTION
# ============================================================

log_section "4. Database Connection Test"

if docker ps --filter "name=mini_soc_db_prod" --filter "status=running" | grep -q "mini_soc_db_prod"; then
    log_info "Database container is running"
    
    log_info "Testing PostgreSQL connection..."
    if docker-compose -f docker-compose.production.yml exec -T db pg_isready -U postgres; then
        echo "  ✓ PostgreSQL is accepting connections"
        
        log_info "Checking database exists..."
        DB_EXISTS=$(docker-compose -f docker-compose.production.yml exec -T db psql -U postgres -lqt 2>/dev/null | grep -c "mini_soc_prod")
        if [ "$DB_EXISTS" -gt 0 ]; then
            echo "  ✓ Database 'mini_soc_prod' exists"
        else
            log_error "  ✗ Database 'mini_soc_prod' NOT FOUND!"
        fi
        
        log_info "Checking migrations..."
        MIGRATIONS=$(docker-compose -f docker-compose.production.yml exec -T db psql -U postgres -d mini_soc_prod -tAc "SELECT COUNT(*) FROM alembic_version" 2>/dev/null || echo "0")
        if [ "$MIGRATIONS" -gt 0 ]; then
            CURRENT_REV=$(docker-compose -f docker-compose.production.yml exec -T db psql -U postgres -d mini_soc_prod -tAc "SELECT version_num FROM alembic_version" 2>/dev/null || echo "none")
            echo "  ✓ Migrations applied: $MIGRATIONS (current: $CURRENT_REV)"
        else
            log_error "  ✗ No migrations applied!"
        fi
    else
        log_error "  ✗ PostgreSQL not accepting connections"
    fi
else
    log_error "Database container is NOT running!"
fi

echo ""

# ============================================================
# 5. REDIS CONNECTION
# ============================================================

log_section "5. Redis Connection Test"

if docker ps --filter "name=mini_soc_redis_prod" --filter "status=running" | grep -q "mini_soc_redis_prod"; then
    log_info "Redis container is running"
    
    REDIS_PASSWORD=$(grep "REDIS_PASSWORD=" .env.production 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "")
    if [ -n "$REDIS_PASSWORD" ]; then
        if docker-compose -f docker-compose.production.yml exec -T redis redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q "PONG"; then
            echo "  ✓ Redis is responding to PING"
        else
            log_error "  ✗ Redis not responding (check password)"
        fi
    else
        log_error "  ✗ REDIS_PASSWORD not found in .env.production"
    fi
else
    log_error "Redis container is NOT running!"
fi

echo ""

# ============================================================
# 6. BACKEND DIAGNOSTICS
# ============================================================

log_section "6. Backend Container Diagnostics"

if docker ps --filter "name=mini_soc_backend_prod" --filter "status=running" | grep -q "mini_soc_backend_prod"; then
    log_info "Backend container is running"
    
    log_info "Backend environment variables (critical only):"
    docker-compose -f docker-compose.production.yml exec -T backend env 2>/dev/null | grep -E "^(ENV|DEBUG|SECRET_KEY|POSTGRES_|REDIS_|WAZUH_|CSRF_)" | head -20
    
    echo ""
    log_info "Backend process check:"
    docker-compose -f docker-compose.production.yml exec -T backend ps aux 2>/dev/null | grep -E "uvicorn|python"
    
    echo ""
    log_info "Backend last 30 log lines:"
    docker-compose -f docker-compose.production.yml logs --tail 30 backend
    
else
    log_error "Backend container is NOT running!"
    log_error "Last logs from backend (if available):"
    docker logs --tail 50 mini_soc_backend_prod 2>/dev/null || echo "  (no logs available)"
fi

echo ""

# ============================================================
# 7. NETWORK CONNECTIVITY
# ============================================================

log_section "7. Network Connectivity"

NGINX_PORT=$(grep "NGINX_PORT=" .env.production 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "2709")

log_info "Testing backend internal endpoint..."
if docker-compose -f docker-compose.production.yml exec -T backend curl -sf http://localhost:8000/api/v1/health/ready >/dev/null 2>&1; then
    echo "  ✓ Backend internal health OK"
else
    log_error "  ✗ Backend internal health FAILED"
    log_error "    Response:"
    docker-compose -f docker-compose.production.yml exec -T backend curl -v http://localhost:8000/api/v1/health/ready 2>&1 | head -20
fi

echo ""
log_info "Testing Nginx proxy..."
if curl -sf http://localhost:$NGINX_PORT/api/v1/health/ready >/dev/null 2>&1; then
    echo "  ✓ Nginx proxy OK"
else
    log_error "  ✗ Nginx proxy FAILED (port $NGINX_PORT)"
    
    log_info "Checking if port is listening..."
    if netstat -tlnp 2>/dev/null | grep -q ":$NGINX_PORT "; then
        echo "  ✓ Port $NGINX_PORT is listening"
    else
        log_error "  ✗ Port $NGINX_PORT NOT listening!"
    fi
fi

echo ""

# ============================================================
# 8. DISK SPACE
# ============================================================

log_section "8. Disk Space Check"
df -h | grep -E "Filesystem|/$|/var"

echo ""

# ============================================================
# 9. DOCKER COMPOSE CONFIG VALIDATION
# ============================================================

log_section "9. Docker Compose Config Validation"

log_info "Validating docker-compose.production.yml..."
if docker-compose -f docker-compose.production.yml config >/dev/null 2>&1; then
    echo "  ✓ docker-compose.production.yml is valid"
else
    log_error "  ✗ docker-compose.production.yml has errors:"
    docker-compose -f docker-compose.production.yml config 2>&1
fi

echo ""

# ============================================================
# SUMMARY
# ============================================================

log_section "=========================================="
log_section "Debug Complete"
log_section "=========================================="

log_info "Next steps:"
echo "1. Review the errors above"
echo "2. Check specific container logs: docker logs <container_name>"
echo "3. Restart specific service: docker-compose -f docker-compose.production.yml restart <service>"
echo "4. Full restart: docker-compose -f docker-compose.production.yml down && docker-compose -f docker-compose.production.yml up -d"
echo "5. Clean rebuild: docker-compose -f docker-compose.production.yml down -v && bash deploy_on_wazuh.sh"
echo ""
