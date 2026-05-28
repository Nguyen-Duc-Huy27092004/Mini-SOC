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
read -p "Enter Nginx port (default: 8080): " NGINX_PORT
NGINX_PORT=${NGINX_PORT:-8080}

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
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

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

# Update port mapping
sed -i "s/- \"80:80\"/- \"$NGINX_PORT:80\"/g" docker-compose.production.yml
sed -i "s/- \"443:443\"/- \"$NGINX_PORT:443\"/g" docker-compose.production.yml || true

log_success "docker-compose.production.yml configured"
echo ""

# ============================================================
# CREATE .env.production
# ============================================================

log_info "Creating .env.production..."

cat > .env.production << EOF
# ========================================
# ENVIRONMENT CONFIGURATION
# ========================================
ENV=production
DEBUG=false

# ========================================
# DATABASE
# ========================================
POSTGRES_USER=postgres
POSTGRES_PASSWORD=$DB_PASSWORD
POSTGRES_DB=mini_soc_prod
POSTGRES_SERVER=db

# ========================================
# REDIS
# ========================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=$REDIS_PASSWORD
REDIS_DB=0

# ========================================
# WAZUH INTEGRATION
# ========================================
WAZUH_ALERTS_FILE=/var/ossec/logs/alerts/alerts.json
WAZUH_ALERTS_HOST_PATH=/var/ossec/logs/alerts

WAZUH_API_URL=$WAZUH_API_URL
WAZUH_API_USER=$WAZUH_USER
WAZUH_API_PASSWORD=$WAZUH_PASSWORD

# ========================================
# APPLICATION
# ========================================
VITE_API_URL=http://$SERVER_IP:$NGINX_PORT/api/v1
VITE_WS_URL=ws://$SERVER_IP:$NGINX_PORT/ws

# ========================================
# SECURITY
# ========================================
SECRET_KEY=$SECRET_KEY
CORS_ORIGINS=http://$SERVER_IP:$NGINX_PORT,http://localhost:$NGINX_PORT
CORS_ALLOW_CREDENTIALS=true

# ========================================
# LOGGING & MONITORING
# ========================================
LOG_LEVEL=INFO
EOF

log_success ".env.production created"
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
# BUILD IMAGES
# ============================================================

log_info "Building Docker images (this may take 5-10 minutes)..."

docker-compose -f docker-compose.production.yml build --no-cache backend
log_success "Backend image built"

docker-compose -f docker-compose.production.yml build --no-cache frontend
log_success "Frontend image built"

echo ""

# ============================================================
# START SERVICES
# ============================================================

log_info "Starting services..."

docker-compose -f docker-compose.production.yml up -d

# Wait for services to be ready
log_info "Waiting for services to start (30 seconds)..."
sleep 30

echo ""

# ============================================================
# VERIFY DEPLOYMENT
# ============================================================

log_info "Verifying deployment..."

# Check services
docker-compose -f docker-compose.production.yml ps

echo ""

# Health check
log_info "Running health checks..."

if curl -s http://localhost/api/v1/health/ready > /dev/null; then
    log_success "Backend health check passed"
else
    log_warn "Backend health check failed (it may still be starting)"
fi

if curl -s http://localhost > /dev/null; then
    log_success "Frontend is accessible"
else
    log_warn "Frontend not responding yet (it may still be starting)"
fi

echo ""

# ============================================================
# CREATE ADMIN USER
# ============================================================

log_info "Creating admin user..."

read -p "Enter admin username (default: admin): " ADMIN_USER
ADMIN_USER=${ADMIN_USER:-"admin"}

read -p "Enter admin email: " ADMIN_EMAIL

read -sp "Enter admin password: " ADMIN_PASSWORD
echo ""

docker-compose -f docker-compose.production.yml exec -T backend \
    python app/scripts/create_admin_user.py << EOF
$ADMIN_USER
$ADMIN_EMAIL
$ADMIN_PASSWORD
EOF

log_success "Admin user created"
echo ""

# ============================================================
# DISPLAY SUMMARY
# ============================================================

log_success "Deployment Complete!"
echo ""
echo "=========================================="
echo "DEPLOYMENT SUMMARY"
echo "=========================================="
echo ""
echo -e "${GREEN}Access URLs:${NC}"
echo "  Web UI:       http://$SERVER_IP:$NGINX_PORT"
echo "  API Docs:     http://$SERVER_IP:$NGINX_PORT/api/v1/docs"
echo "  Health:       http://$SERVER_IP:$NGINX_PORT/api/v1/health/ready"
echo ""
echo -e "${GREEN}Credentials:${NC}"
echo "  Admin User:   $ADMIN_USER"
echo "  Admin Email:  $ADMIN_EMAIL"
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Deployment:   $DEPLOY_PATH"
echo "  Port:         $NGINX_PORT"
echo "  Server IP:    $SERVER_IP"
echo "  Wazuh API:    $WAZUH_API_URL"
echo ""
echo -e "${GREEN}Database:${NC}"
echo "  PostgreSQL:   $DEPLOY_PATH/.env.production"
echo "  Redis:        $DEPLOY_PATH/.env.production"
echo ""
echo "=========================================="
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "1. Open browser: http://$SERVER_IP:$NGINX_PORT"
echo "2. Login with admin credentials"
echo "3. Check Wazuh alerts in dashboard"
echo "4. Monitor logs: docker-compose -f docker-compose.production.yml logs -f"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo "  View logs:        docker-compose -f docker-compose.production.yml logs -f"
echo "  Restart:          docker-compose -f docker-compose.production.yml restart"
echo "  Stop all:         docker-compose -f docker-compose.production.yml down"
echo "  View config:      cat .env.production"
echo ""
echo -e "${YELLOW}Important:${NC}"
echo "- Save passwords from .env.production"
echo "- Keep backup of docker-compose.production.yml.bak"
echo "- Monitor system resources: docker stats"
echo "- Check firewall allows port $NGINX_PORT"
echo ""
