#!/bin/bash

# ============================================================
# Mini-SOC Deployment Script on Wazuh Server
# ============================================================
# Hướng dẫn triển khai tự động Mini-SOC trên server có Wazuh
# Usage: sudo bash deploy_on_wazuh.sh
# ============================================================

set -e

# ============================================================
# COLORS
# ============================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================
# FUNCTIONS
# ============================================================

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

# ============================================================
# PRE-FLIGHT CHECKS
# ============================================================

log_info "Starting Mini-SOC Deployment on Wazuh Server..."
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
   log_error "This script must be run as root (use: sudo bash deploy_on_wazuh.sh)"
   exit 1
fi

log_info "Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed"
    exit 1
fi
log_success "Docker found: $(docker --version)"

# Check Docker Compose
if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed"
    exit 1
fi
log_success "Docker Compose found: $(docker-compose --version)"

# Check Git
if ! command -v git &> /dev/null; then
    log_error "Git is not installed"
    exit 1
fi
log_success "Git found: $(git --version)"

# Check if Wazuh is running
if ! netstat -tlnp | grep -q ":55000\|:1514\|:514"; then
    log_warn "Wazuh ports not found. Make sure Wazuh is running on this server"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
log_success "Wazuh appears to be running"

echo ""

# ============================================================
# CONFIGURATION
# ============================================================

log_info "Configuration Setup"
echo ""

# Get deployment path
read -p "Enter deployment path (default: /opt/mini-soc): " DEPLOY_PATH
DEPLOY_PATH=${DEPLOY_PATH:-/opt/mini-soc}

# Get port
read -p "Enter Nginx port (default: 2709): " NGINX_PORT
NGINX_PORT=${NGINX_PORT:-2709}

# Check if port is available
if netstat -tlnp 2>/dev/null | grep -q ":$NGINX_PORT "; then
    log_error "Port $NGINX_PORT is already in use"
    exit 1
fi

# Get server IP
CURRENT_IP=$(hostname -I | awk '{print $1}')
read -p "Enter server IP for access (default: $CURRENT_IP): " SERVER_IP
SERVER_IP=${SERVER_IP:-$CURRENT_IP}

# Get Wazuh API details
read -p "Enter Wazuh API URL (default: http://$CURRENT_IP:55000): " WAZUH_API_URL
WAZUH_API_URL=${WAZUH_API_URL:-"http://$CURRENT_IP:55000"}

read -p "Enter Wazuh API username (default: wazuh): " WAZUH_USER
WAZUH_USER=${WAZUH_USER:-"wazuh"}

read -sp "Enter Wazuh API password: " WAZUH_PASSWORD
echo ""

# Generate passwords
DB_PASSWORD=$(openssl rand -base64 32)
REDIS_PASSWORD=$(openssl rand -base64 32)
# Use secrets module if available (Python 3.6+), fallback to openssl
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)

# Export variables for Python subprocess
export NGINX_PORT DB_PASSWORD REDIS_PASSWORD SECRET_KEY
export SERVER_IP WAZUH_API_URL WAZUH_USER WAZUH_PASSWORD

log_success "Configuration generated"
echo ""

# ============================================================
# SETUP DIRECTORIES
# ============================================================

log_info "Setting up directories..."

if [ -d "$DEPLOY_PATH" ]; then
    log_warn "Directory $DEPLOY_PATH already exists"
    read -p "Continue with existing directory? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    mkdir -p "$DEPLOY_PATH"
    log_success "Directory created: $DEPLOY_PATH"
fi

cd "$DEPLOY_PATH"

# ============================================================
# CLONE REPOSITORY
# ============================================================

if [ ! -d ".git" ]; then
    log_info "Cloning repository..."
    read -p "Enter repository URL: " REPO_URL
    git clone "$REPO_URL" .
    log_success "Repository cloned"
else
    log_info "Repository already exists, pulling latest..."
    git pull origin main
    log_success "Repository updated"
fi

echo ""

# ============================================================
# CONFIGURE DOCKER COMPOSE
# ============================================================

log_info "Configuring docker-compose.production.yml..."

# Backup original
cp docker-compose.production.yml docker-compose.production.yml.bak

# docker-compose.production.yml already uses ${NGINX_PORT:-2709} parameterization.
# No need to rewrite the YAML file.

log_success "docker-compose.production.yml configured"
echo ""

# ============================================================
# CREATE .env.production
# ============================================================

log_info "Determining Wazuh alerts mount path..."
if [ -d "/var/ossec/logs/alerts" ]; then
    WAZUH_MOUNT_PATH="/var/ossec/logs/alerts"
else
    WAZUH_MOUNT_PATH="$DEPLOY_PATH/data/wazuh"
fi

log_info "Creating .env.production..."

cat > .env.production << EOF
# ========================================
# MINI SOC PRODUCTION CONFIGURATION
# ========================================
# This file is automatically generated during deployment
# Last updated: $(date)

# =========================================================
# CORE SETTINGS
# =========================================================

PROJECT_NAME="Mini SOC Portal"
ENV="production"
DEBUG="false"
API_V1_STR="/api/v1"
LOG_LEVEL="INFO"

# =========================================================
# SECURITY
# =========================================================

# JWT Configuration
SECRET_KEY="$SECRET_KEY"
ACCESS_TOKEN_EXPIRE_MINUTES="15"
REFRESH_TOKEN_EXPIRE_DAYS="7"
WS_TICKET_EXPIRE_SECONDS="60"

# Rate Limiting
LOGIN_RATE_LIMIT_PER_MINUTE="10"
RATE_LIMIT_PER_MINUTE="100"
WS_RATE_LIMIT_PER_MINUTE="120"

# CORS Configuration
BACKEND_CORS_ORIGINS="http://$SERVER_IP:$NGINX_PORT,http://localhost:$NGINX_PORT,http://127.0.0.1:$NGINX_PORT"

# Cookie Security
COOKIE_SECURE="false"
COOKIE_DOMAIN=""
CSRF_VALIDATE_ORIGIN="false"

# Default Admin Password (CHANGE AFTER FIRST LOGIN)
DEFAULT_ADMIN_PASSWORD="ChangeMe123!"

# =========================================================
# DATABASE (PostgreSQL)
# =========================================================

POSTGRES_SERVER="db"
POSTGRES_PORT="5432"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="$DB_PASSWORD"
POSTGRES_DB="mini_soc_prod"

# Database Connection Pool
DB_POOL_SIZE="20"
DB_MAX_OVERFLOW="40"
DB_POOL_TIMEOUT="30"
DB_POOL_RECYCLE="1800"

# =========================================================
# REDIS
# =========================================================

REDIS_HOST="redis"
REDIS_PORT="6379"
REDIS_PASSWORD="$REDIS_PASSWORD"
REDIS_DB="0"

# =========================================================
# OPENSEARCH
# =========================================================

OPENSEARCH_HOSTS="https://opensearch:9200"
OPENSEARCH_USER="admin"
OPENSEARCH_PASSWORD="admin"
OPENSEARCH_VERIFY_CERTS="false"
OPENSEARCH_SSL_SHOW_WARN="false"

# =========================================================
# WAZUH INTEGRATION
# =========================================================

# Wazuh API Configuration
WAZUH_API_URL="$WAZUH_API_URL"
WAZUH_API_USER="$WAZUH_USER"
WAZUH_API_PASSWORD="$WAZUH_PASSWORD"
WAZUH_VERIFY_SSL="false"

# Wazuh Alerts File
WAZUH_ALERTS_FILE="/var/ossec/logs/alerts/alerts.json"

# =========================================================
# GEOIP
# =========================================================

GEOIP_DB_PATH="/usr/share/GeoIP/GeoLite2-City.mmdb"

# =========================================================
# OBSERVABILITY
# =========================================================

ENABLE_SENTRY="false"
SENTRY_DSN=""

# =========================================================
# APPLICATION URLs
# =========================================================

# Frontend Configuration
FRONTEND_URL="http://$SERVER_IP:$NGINX_PORT"
VITE_API_URL="http://$SERVER_IP:$NGINX_PORT/api/v1"
VITE_WS_URL="ws://$SERVER_IP:$NGINX_PORT/ws"

# Backend Configuration  
BACKEND_URL="http://$SERVER_IP:$NGINX_PORT"
HOST="0.0.0.0"
PORT="8000"
WORKERS="4"

# =========================================================
# DEPLOYMENT INFO & DOCKER VOLUMES
# =========================================================

NGINX_PORT="$NGINX_PORT"

# Wazuh Alerts Mount Path
WAZUH_ALERTS_HOST_PATH="$WAZUH_MOUNT_PATH"

# Deployed at: $DEPLOY_PATH
# Nginx Port: $NGINX_PORT
# Server IP: $SERVER_IP
# Deployment Date: $(date)

EOF

log_success ".env.production created"
echo ""
log_info "Configuration file details:"
echo "  - SECRET_KEY: Generated"
echo "  - Database Password: Generated"
echo "  - Redis Password: Generated"
echo "  - Wazuh API: $WAZUH_API_URL"
echo "  - Server Access: http://$SERVER_IP:$NGINX_PORT"
echo ""

# Verify .env.production was created successfully
if [ ! -f ".env.production" ]; then
    log_error ".env.production file was not created!"
    exit 1
fi

# Verify critical variables in .env.production
log_info "Verifying .env.production content..."
if ! grep -q "POSTGRES_PASSWORD=" .env.production; then
    log_error "POSTGRES_PASSWORD not found in .env.production"
    exit 1
fi
if ! grep -q "REDIS_PASSWORD=" .env.production; then
    log_error "REDIS_PASSWORD not found in .env.production"
    exit 1
fi
if ! grep -q "SECRET_KEY=" .env.production; then
    log_error "SECRET_KEY not found in .env.production"
    exit 1
fi
log_success "All required variables verified in .env.production"
echo ""

# ============================================================
# CHECK WAZUH ALERTS FILE
# ============================================================

log_info "Checking Wazuh alerts file..."

if [ -f "/var/ossec/logs/alerts/alerts.json" ]; then
    log_success "Found Wazuh alerts at /var/ossec/logs/alerts/alerts.json"
    
    # Check permissions
    if [ ! -r "/var/ossec/logs/alerts/alerts.json" ]; then
        log_warn "Fixing permissions for alerts file..."
        chmod 755 /var/ossec/logs/alerts
        chmod 644 /var/ossec/logs/alerts/alerts.json
        log_success "Permissions fixed"
    fi
else
    log_warn "Wazuh alerts file not found at expected location"
    log_info "Mini-SOC will try to use Wazuh API instead"
fi

echo ""

# ============================================================
# CLEANUP OLD CONTAINERS
# ============================================================

log_info "Cleaning up old containers and images..."

# Stop and remove old containers
docker-compose -f docker-compose.production.yml down -v 2>/dev/null || true

# Remove dangling images
docker image prune -f --filter "dangling=true" || true

log_success "Cleanup complete"
echo ""

# ============================================================
# CREATE WAZUH ALERTS DIRECTORY
# ============================================================

log_info "Creating Wazuh alerts mount directory..."
mkdir -p "$DEPLOY_PATH/data/wazuh"
chmod 755 "$DEPLOY_PATH/data/wazuh"
log_success "Wazuh data directory created"
echo ""

# ============================================================
# BUILD IMAGES
# ============================================================

log_info "Building Docker images (this may take 5-10 minutes)..."
log_info "Using .env.production from: $PWD/.env.production"

# Export environment variables to be used by docker-compose
set -a
if ! source .env.production 2>/dev/null; then
    log_error ".env.production has syntax errors! Check file format."
    cat .env.production | head -20
    exit 1
fi
set +a

log_success "Environment variables loaded successfully"

# Build backend first
log_info "Building backend image..."
if ! docker-compose -f docker-compose.production.yml build backend 2>&1 | tee /tmp/backend_build.log; then
    log_error "Backend build failed! Check logs:"
    tail -50 /tmp/backend_build.log
    exit 1
fi
log_success "Backend image built"

# Build frontend
log_info "Building frontend image..."
if ! docker-compose -f docker-compose.production.yml build frontend 2>&1 | tee /tmp/frontend_build.log; then
    log_error "Frontend build failed! Check logs:"
    tail -50 /tmp/frontend_build.log
    exit 1
fi
log_success "Frontend image built"

echo ""

# ============================================================
# START DATABASE & REDIS FIRST
# ============================================================

log_info "Starting database and Redis services first..."

docker-compose -f docker-compose.production.yml up -d db redis

log_info "Waiting for database to be ready..."
DB_READY=false
for i in {1..60}; do
    if docker-compose -f docker-compose.production.yml exec -T db pg_isready -U postgres &> /dev/null; then
        log_success "✓ PostgreSQL is ready"
        DB_READY=true
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

if [ "$DB_READY" = false ]; then
    log_error "Database failed to start after 120 seconds. Showing logs:"
    docker-compose -f docker-compose.production.yml logs db
    exit 1
fi

# Wait for Redis
log_info "Waiting for Redis..."
REDIS_READY=false
for i in {1..30}; do
    if docker-compose -f docker-compose.production.yml exec -T redis redis-cli -a "$REDIS_PASSWORD" ping &> /dev/null 2>&1; then
        log_success "✓ Redis is ready"
        REDIS_READY=true
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

if [ "$REDIS_READY" = false ]; then
    log_warn "Redis authentication check failed (this may be normal during startup)"
fi

echo ""

# ============================================================
# RUN DATABASE MIGRATIONS BEFORE BACKEND STARTS
# ============================================================

log_info "Running database migrations BEFORE starting backend..."

# Run migrations using one-off container
if ! docker-compose -f docker-compose.production.yml run --rm \
    -e POSTGRES_SERVER=db \
    -e POSTGRES_PASSWORD="$DB_PASSWORD" \
    -e SECRET_KEY="$SECRET_KEY" \
    backend sh -c "alembic upgrade head" 2>&1 | tee /tmp/migration.log; then
    log_error "Database migration failed! Check logs:"
    cat /tmp/migration.log
    docker-compose -f docker-compose.production.yml logs db
    exit 1
fi

log_success "✅ Database migrations completed SUCCESSFULLY"
echo ""

# ============================================================
# START REMAINING SERVICES
# ============================================================

log_info "Starting backend, frontend, and nginx..."

# Verify docker-compose config is valid
if ! docker-compose -f docker-compose.production.yml config &> /dev/null; then
    log_error "Docker compose configuration error. Check .env.production format"
    docker-compose -f docker-compose.production.yml config
    exit 1
fi

# Start all services
docker-compose -f docker-compose.production.yml up -d

log_info "Waiting for backend to be ready..."
log_info "Backend has 15s start_period + health checks"

# Wait for backend health
BACKEND_READY=false
for i in {1..60}; do
    if curl -sf http://localhost:8000/api/v1/health/ready > /dev/null 2>&1; then
        log_success "✓ Backend is healthy"
        BACKEND_READY=true
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

if [ "$BACKEND_READY" = false ]; then
    log_error "Backend failed to start. Showing logs:"
    docker-compose -f docker-compose.production.yml logs --tail=100 backend
    exit 1
fi

# Wait for nginx
log_info "Waiting for Nginx..."
NGINX_READY=false
for i in {1..30}; do
    if curl -sf http://localhost:$NGINX_PORT/api/v1/health/ready > /dev/null 2>&1; then
        log_success "✓ Nginx is serving requests"
        NGINX_READY=true
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

if [ "$NGINX_READY" = false ]; then
    log_warn "Nginx not responding yet (frontend may still be building)"
fi

echo ""

# ============================================================
# VERIFY DEPLOYMENT
# ============================================================

log_info "Final deployment verification..."

# Check all services status
docker-compose -f docker-compose.production.yml ps

echo ""

# ============================================================
# CREATE ADMIN USER
# ============================================================

log_info "Creating admin user..."
echo ""

read -p "Enter admin username (default: admin): " ADMIN_USER
ADMIN_USER=${ADMIN_USER:-"admin"}

while true; do
    read -p "Enter admin email: " ADMIN_EMAIL
    if [[ "$ADMIN_EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        break
    else
        log_error "Invalid email format. Please try again."
    fi
done

while true; do
    read -sp "Enter admin password (min 8 characters): " ADMIN_PASSWORD
    echo ""
    if [ ${#ADMIN_PASSWORD} -ge 8 ]; then
        break
    else
        log_error "Password must be at least 8 characters"
    fi
done

log_info "Creating admin user in database..."
if docker-compose -f docker-compose.production.yml exec -T backend \
    python -c "import sys; sys.path.insert(0, '/app'); from app.scripts.create_admin_user import main; import asyncio; asyncio.run(main())" \
    --email "$ADMIN_EMAIL" \
    --password "$ADMIN_PASSWORD" \
    --user "$ADMIN_USER" 2>&1 | tee /tmp/create_admin.log; then
    log_success "✅ Admin user created successfully"
else
    log_warn "Admin user creation may have failed. Check output above."
    log_info "You can create admin manually later by running:"
    echo "  docker-compose -f docker-compose.production.yml exec backend python app/scripts/create_admin_user.py --email <email> --password <password>"
fi

echo ""

# ============================================================
# DISPLAY SUMMARY
# ============================================================

log_success "Deployment Complete!"
echo ""
echo "==========================================================="
echo "  🎉 MINI-SOC DEPLOYMENT SUMMARY 🎉"
echo "==========================================================="
echo ""
echo -e "${GREEN}📍 Access URLs:${NC}"
echo "  Web UI:           http://$SERVER_IP:$NGINX_PORT"
echo "  API Documentation: http://$SERVER_IP:$NGINX_PORT/api/v1/docs (If DEBUG=true)"
echo "  Health Check:     http://$SERVER_IP:$NGINX_PORT/api/v1/health/ready"
echo ""
echo -e "${GREEN}👤 Credentials:${NC}"
echo "  Admin User:       $ADMIN_USER"
echo "  Admin Email:      $ADMIN_EMAIL"
echo "  Password:         (stored securely)"
echo ""
echo -e "${GREEN}🔧 Configuration:${NC}"
echo "  Deployment Path:  $DEPLOY_PATH"
echo "  Access Port:      $NGINX_PORT"
echo "  Server IP:        $SERVER_IP"
echo "  Wazuh API:        $WAZUH_API_URL"
echo "  Env File:         $DEPLOY_PATH/.env.production"
echo ""
echo -e "${GREEN}🗄️  Database & Cache:${NC}"
echo "  PostgreSQL:       Running in container (db)"
echo "  Redis:            Running in container (redis)"
echo "  OpenSearch:       Running in container (opensearch)"
echo ""
echo "==========================================================="
echo ""
echo -e "${BLUE}✅ Next Steps:${NC}"
echo "1. Open browser: http://$SERVER_IP:$NGINX_PORT"
echo "2. Login with admin credentials"
echo "3. Verify Wazuh alerts are being collected"
echo "4. Check system monitoring dashboard"
echo ""
echo -e "${BLUE}📋 Useful Commands:${NC}"
echo "  View logs:        docker-compose -f docker-compose.production.yml logs -f backend"
echo "  Restart service:  docker-compose -f docker-compose.production.yml restart"
echo "  Stop all:         docker-compose -f docker-compose.production.yml down"
echo "  View config:      cat .env.production"
echo "  Container stats:  docker stats"
echo ""
echo -e "${YELLOW}⚠️  Important Notes:${NC}"
echo "• Save all passwords from .env.production in a secure location"
echo "• Keep backup: docker-compose.production.yml.bak"
echo "• Monitor system resources regularly: docker stats"
echo "• Ensure firewall allows port $NGINX_PORT (TCP)"
echo "• Change admin password immediately after first login"
echo "• Regularly backup PostgreSQL data: docker-compose exec db pg_dump -U postgres mini_soc_prod"
echo ""
echo "==========================================================="
echo ""
