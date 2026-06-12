#!/bin/bash

# ============================================================
# Auto-Fix Wazuh Connection
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[⚠]${NC} $1"; }
log_section() { echo -e "\n${GREEN}════════════════════════════════════════${NC}\n${GREEN}$1${NC}\n${GREEN}════════════════════════════════════════${NC}\n"; }

log_section "AUTO-FIX WAZUH CONNECTION"

# ============================================================
# COLLECT REQUIRED INFORMATION
# ============================================================

log_section "STEP 1: THÔNG TIN CẤU HÌNH"

# Wazuh API Information
read -p "Enter Wazuh API URL (e.g., https://192.168.1.100:55000): " WAZUH_API_URL
if [ -z "$WAZUH_API_URL" ]; then
    log_error "Wazuh API URL is required!"
    exit 1
fi

read -p "Enter Wazuh API username (default: wazuh): " WAZUH_API_USER
WAZUH_API_USER=${WAZUH_API_USER:-"wazuh"}

read -sp "Enter Wazuh API password: " WAZUH_API_PASSWORD
echo ""
if [ -z "$WAZUH_API_PASSWORD" ]; then
    log_error "Password is required!"
    exit 1
fi

# Alerts file location
read -p "Enter Wazuh alerts file path (default: /var/ossec/logs/alerts/alerts.json): " WAZUH_ALERTS_FILE
WAZUH_ALERTS_FILE=${WAZUH_ALERTS_FILE:-"/var/ossec/logs/alerts/alerts.json"}

# SSL verification
read -p "Verify SSL? (y/n, default: n): " VERIFY_SSL
WAZUH_VERIFY_SSL="false"
if [[ "$VERIFY_SSL" =~ ^[Yy]$ ]]; then
    WAZUH_VERIFY_SSL="true"
fi

# Server info
read -p "Enter your server IP/hostname: " SERVER_IP
if [ -z "$SERVER_IP" ]; then
    SERVER_IP=$(hostname -I | awk '{print $1}')
    log_info "Using detected IP: $SERVER_IP"
fi

read -p "Enter Nginx port (default: 2709): " NGINX_PORT
NGINX_PORT=${NGINX_PORT:-"2709"}

# Database password
read -sp "Enter database password (press Enter for auto-generate): " DB_PASSWORD
if [ -z "$DB_PASSWORD" ]; then
    DB_PASSWORD=$(openssl rand -base64 32)
    log_info "Generated database password"
fi
echo ""

# Redis password
read -sp "Enter Redis password (press Enter for auto-generate): " REDIS_PASSWORD
if [ -z "$REDIS_PASSWORD" ]; then
    REDIS_PASSWORD=$(openssl rand -base64 32)
    log_info "Generated Redis password"
fi
echo ""

# Secret key
read -sp "Enter SECRET_KEY (press Enter for auto-generate): " SECRET_KEY
if [ -z "$SECRET_KEY" ]; then
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
    log_info "Generated SECRET_KEY"
fi
echo ""

# ============================================================
# VERIFY INPUTS
# ============================================================

log_section "STEP 2: XÁC MINH THÔNG TIN"

echo "Configuration Summary:"
echo "  Wazuh API URL: $WAZUH_API_URL"
echo "  Wazuh User: $WAZUH_API_USER"
echo "  Wazuh Alerts File: $WAZUH_ALERTS_FILE"
echo "  SSL Verify: $WAZUH_VERIFY_SSL"
echo "  Server IP: $SERVER_IP"
echo "  Nginx Port: $NGINX_PORT"
echo "  Database Password: (set)"
echo "  Redis Password: (set)"
echo ""

read -p "Continue with this configuration? (y/n): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    log_error "Cancelled"
    exit 1
fi

# ============================================================
# TEST WAZUH CONNECTION
# ============================================================

log_section "STEP 3: KIỂM TRA KẾT NỐI WAZUH"

log_info "Testing Wazuh API connection..."
if curl -s -k -u "$WAZUH_API_USER:$WAZUH_API_PASSWORD" -X GET "$WAZUH_API_URL/api/summary" 2>/dev/null | grep -q '"agents"'; then
    log_success "Wazuh API connection successful!"
else
    log_warn "Could not connect to Wazuh API - continuing anyway"
    log_warn "Please verify credentials after setup"
fi

# ============================================================
# CREATE .env.production
# ============================================================

log_section "STEP 4: TẠO .env.production"

cat > .env.production << EOF
# ========================================
# MINI SOC PRODUCTION CONFIGURATION
# ========================================
# Generated: $(date)

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

SECRET_KEY="$SECRET_KEY"
ACCESS_TOKEN_EXPIRE_MINUTES="15"
REFRESH_TOKEN_EXPIRE_DAYS="7"
WS_TICKET_EXPIRE_SECONDS="60"

LOGIN_RATE_LIMIT_PER_MINUTE="10"
RATE_LIMIT_PER_MINUTE="100"
WS_RATE_LIMIT_PER_MINUTE="120"

BACKEND_CORS_ORIGINS="http://$SERVER_IP:$NGINX_PORT,http://localhost:$NGINX_PORT,http://127.0.0.1:$NGINX_PORT"

COOKIE_SECURE="false"
COOKIE_DOMAIN=""
CSRF_VALIDATE_ORIGIN="false"

DEFAULT_ADMIN_PASSWORD="ChangeMe123!"

# =========================================================
# DATABASE (PostgreSQL)
# =========================================================

POSTGRES_SERVER="db"
POSTGRES_PORT="5432"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="$DB_PASSWORD"
POSTGRES_DB="mini_soc"

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

# =========================================================
# WAZUH INTEGRATION (CRITICAL!)
# =========================================================

WAZUH_API_URL="$WAZUH_API_URL"
WAZUH_API_USER="$WAZUH_API_USER"
WAZUH_API_PASSWORD="$WAZUH_API_PASSWORD"
WAZUH_VERIFY_SSL="$WAZUH_VERIFY_SSL"
WAZUH_ALERTS_FILE="$WAZUH_ALERTS_FILE"

# =========================================================
# GEOIP
# =========================================================

GEOIP_DB_PATH="/usr/share/GeoIP/GeoLite2-City.mmdb"

# =========================================================
# OBSERVABILITY
# =========================================================

ENABLE_SENTRY="false"
SENTRY_DSN=""
EOF

log_success ".env.production created"

# ============================================================
# UPDATE docker-compose.production.yml
# ============================================================

log_section "STEP 5: CẬP NHẬT DOCKER-COMPOSE"

# Check if volume is already present
if grep -q "/var/ossec/logs/alerts" docker-compose.production.yml; then
    log_info "Volume already configured in docker-compose.production.yml"
else
    log_info "Adding Wazuh volume to docker-compose.production.yml..."
    
    # Backup original
    cp docker-compose.production.yml docker-compose.production.yml.bak
    
    # Add volume mount to backend service
    # This is a simple approach - may need manual adjustment for complex YAML
    python3 << 'PYSCRIPT'
import yaml
import sys

try:
    with open('docker-compose.production.yml', 'r') as f:
        compose = yaml.safe_load(f)
    
    if 'services' in compose and 'backend' in compose['services']:
        if 'volumes' not in compose['services']['backend']:
            compose['services']['backend']['volumes'] = []
        
        # Add volume if not present
        volume_mount = '/var/ossec/logs/alerts:/var/ossec/logs/alerts:ro'
        if volume_mount not in compose['services']['backend']['volumes']:
            compose['services']['backend']['volumes'].append(volume_mount)
        
        with open('docker-compose.production.yml', 'w') as f:
            yaml.dump(compose, f, default_flow_style=False)
        
        print("Updated docker-compose.production.yml")
    else:
        print("ERROR: Could not find backend service in docker-compose.production.yml")
        sys.exit(1)
        
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
PYSCRIPT
    
    if [ $? -eq 0 ]; then
        log_success "Docker-compose updated"
    else
        log_warn "Could not automatically update docker-compose.production.yml"
        log_warn "Please manually add this to backend service volumes:"
        log_warn "  - /var/ossec/logs/alerts:/var/ossec/logs/alerts:ro"
    fi
fi

# ============================================================
# DOCKER RESTART
# ============================================================

log_section "STEP 6: KHỞI ĐỘNG LẠI DOCKER"

read -p "Restart Docker containers now? (y/n): " RESTART_DOCKER
if [[ "$RESTART_DOCKER" =~ ^[Yy]$ ]]; then
    log_info "Stopping containers..."
    docker-compose -f docker-compose.production.yml down
    
    log_info "Starting containers..."
    docker-compose -f docker-compose.production.yml up -d
    
    log_info "Waiting for services to start..."
    sleep 15
    
    log_info "Checking backend logs..."
    docker logs mini_soc_backend_prod 2>&1 | tail -20 | grep -E "collector|WAZUH|running" || true
else
    log_warn "Remember to restart Docker containers with:"
    log_warn "  docker-compose -f docker-compose.production.yml down"
    log_warn "  docker-compose -f docker-compose.production.yml up -d"
fi

# ============================================================
# VERIFICATION
# ============================================================

log_section "STEP 7: XÁC MINH"

read -p "Run diagnostic check? (y/n): " RUN_DIAG
if [[ "$RUN_DIAG" =~ ^[Yy]$ ]]; then
    if [ -f "DIAGNOSE_WAZUH_CONNECTION.sh" ]; then
        bash DIAGNOSE_WAZUH_CONNECTION.sh
    else
        log_warn "DIAGNOSE_WAZUH_CONNECTION.sh not found"
    fi
fi

log_section "HOÀN TẤT!"

echo "✅ Configuration complete!"
echo ""
echo "Next steps:"
echo "1. Check logs: docker logs -f mini_soc_backend_prod | grep collector"
echo "2. System should start collecting Wazuh alerts"
echo "3. Change default admin password after first login"
echo ""
log_success "For more help, see: WAZUH_CONNECTION_FIX.md"
