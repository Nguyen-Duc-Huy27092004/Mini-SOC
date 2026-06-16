#!/bin/bash
# =======================================================================
#  Mini-SOC — Full Deployment Script (Wazuh + Zabbix)
#  Target OS : Ubuntu/Debian Linux (Wazuh server)
#  Usage     : sudo bash deploy_on_wazuh.sh
#  Version   : 4.0 (hardened, idempotent, zero-conflict ports)
# =======================================================================
set -euo pipefail
IFS=$'\n\t'

# -----------------------------------------------------------------------
# COLOUR HELPERS
# -----------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_ok()      { echo -e "${GREEN}[✓]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[⚠]${NC}    $*"; }
log_error()   { echo -e "${RED}[✗]${NC}    $*"; }
log_section() {
    echo -e "\n${BOLD}${CYAN}══════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  $*${NC}"
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════════${NC}\n"
}
die() { log_error "$*"; exit 1; }

# -----------------------------------------------------------------------
# MUST BE ROOT
# -----------------------------------------------------------------------
[[ "$EUID" -ne 0 ]] && die "Run as root: sudo bash deploy_on_wazuh.sh"

# -----------------------------------------------------------------------
# DETECT DOCKER COMPOSE COMMAND (v1 or v2)
# -----------------------------------------------------------------------
if docker compose version &>/dev/null 2>&1; then
    DC="docker compose"
elif command -v docker-compose &>/dev/null; then
    DC="docker-compose"
else
    die "Neither 'docker compose' nor 'docker-compose' is available. Install Docker (>= 20.10)."
fi
log_ok "Docker Compose detected: $DC"

# -----------------------------------------------------------------------
# PRE-FLIGHT CHECKS
# -----------------------------------------------------------------------
log_section "PRE-FLIGHT CHECKS"

command -v docker  &>/dev/null || die "Docker not installed."
log_ok "Docker: $(docker --version)"
log_ok "Compose: $($DC version --short 2>/dev/null || $DC version | head -1)"
command -v git     &>/dev/null || die "git not installed."
log_ok "Git: $(git --version)"
command -v curl    &>/dev/null || die "curl not installed."
command -v openssl &>/dev/null || die "openssl not installed."

# -----------------------------------------------------------------------
# WELL-KNOWN PORTS USED BY WAZUH & SYSTEM — NEVER TOUCH THESE
# -----------------------------------------------------------------------
RESERVED_PORTS=(22 80 443 514 1514 1515 1516 5601 9200 9300 9600 55000)

is_port_reserved() {
    local p="$1"
    for r in "${RESERVED_PORTS[@]}"; do
        [[ "$p" == "$r" ]] && return 0
    done
    return 1
}

is_port_in_use() {
    local p="$1"
    if command -v ss &>/dev/null; then
        ss -tlnp 2>/dev/null | grep -q ":${p} " && return 0 || return 1
    else
        netstat -tlnp 2>/dev/null | grep -q ":${p} " && return 0 || return 1
    fi
}

# -----------------------------------------------------------------------
# WAZUH DETECTION (informational — we do NOT stop if Wazuh isn't running)
# -----------------------------------------------------------------------
log_info "Checking Wazuh presence..."
WAZUH_RUNNING=false
if is_port_in_use 55000 || is_port_in_use 1514; then
    WAZUH_RUNNING=true
    log_ok "Wazuh appears to be running (port 55000 or 1514 detected)"
else
    log_warn "Wazuh ports not detected — Wazuh may not be running on this server"
    log_warn "Mini-SOC will start but Wazuh data will be unavailable until Wazuh is live"
fi

# -----------------------------------------------------------------------
# CONFIGURATION — INTERACTIVE
# -----------------------------------------------------------------------
log_section "CONFIGURATION"

# Deployment path
read -rp "Deployment path [default: /opt/mini-soc]: " DEPLOY_PATH
DEPLOY_PATH="${DEPLOY_PATH:-/opt/mini-soc}"

# Choose Mini-SOC port (must not conflict with anything)
while true; do
    read -rp "Mini-SOC Nginx port [default: 2709]: " NGINX_PORT
    NGINX_PORT="${NGINX_PORT:-2709}"
    if is_port_reserved "$NGINX_PORT"; then
        log_error "Port $NGINX_PORT is reserved for Wazuh or system services. Choose another."
    elif is_port_in_use "$NGINX_PORT"; then
        log_error "Port $NGINX_PORT is already in use. Choose another."
    else
        log_ok "Port $NGINX_PORT is available"
        break
    fi
done

# Server IP
CURRENT_IP=$(hostname -I | awk '{print $1}')
read -rp "Server IP / hostname [default: $CURRENT_IP]: " SERVER_IP
SERVER_IP="${SERVER_IP:-$CURRENT_IP}"

# ──── WAZUH ────
echo ""
log_info "Wazuh API credentials (used to pull agent data):"
read -rp "  Wazuh API URL   [default: https://$CURRENT_IP:55000]: " WAZUH_API_URL
WAZUH_API_URL="${WAZUH_API_URL:-"https://$CURRENT_IP:55000"}"
read -rp "  Wazuh API user  [default: wazuh]: " WAZUH_API_USER
WAZUH_API_USER="${WAZUH_API_USER:-wazuh}"
read -rsp "  Wazuh API password: " WAZUH_API_PASSWORD; echo ""
[[ -z "$WAZUH_API_PASSWORD" ]] && die "Wazuh API password cannot be empty."

# ──── ZABBIX ────
echo ""
log_info "Zabbix API credentials (leave URL empty to disable Zabbix):"
read -rp "  Zabbix API URL  [e.g. http://$CURRENT_IP/zabbix/api_jsonrpc.php, or ENTER to disable]: " ZABBIX_API_URL
if [[ -z "$ZABBIX_API_URL" ]]; then
    ZABBIX_ENABLED="false"
    ZABBIX_API_USER="Admin"
    ZABBIX_API_PASSWORD="zabbix"
    ZABBIX_API_URL="http://localhost/zabbix/api_jsonrpc.php"
    log_warn "Zabbix disabled. You can enable it later by updating .env.production"
else
    ZABBIX_ENABLED="true"
    read -rp "  Zabbix user     [default: Admin]: " ZABBIX_API_USER
    ZABBIX_API_USER="${ZABBIX_API_USER:-Admin}"
    read -rsp "  Zabbix password: " ZABBIX_API_PASSWORD; echo ""
    [[ -z "$ZABBIX_API_PASSWORD" ]] && die "Zabbix password cannot be empty when Zabbix is enabled."
    log_ok "Zabbix enabled → $ZABBIX_API_URL"
fi

# ──── ADMIN USER ────
echo ""
log_info "Mini-SOC admin account:"
read -rp "  Admin username  [default: admin]: " ADMIN_USER
ADMIN_USER="${ADMIN_USER:-admin}"

while true; do
    read -rp "  Admin email: " ADMIN_EMAIL
    [[ "$ADMIN_EMAIL" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]] && break
    log_error "Invalid email format, try again."
done

while true; do
    read -rsp "  Admin password (min 8 chars): " ADMIN_PASSWORD; echo ""
    [[ ${#ADMIN_PASSWORD} -ge 8 ]] && break
    log_error "Password too short (< 8 chars)."
done

# ──── GENERATE SECRETS ────
DB_PASSWORD=$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 40)
REDIS_PASSWORD=$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 40)
SECRET_KEY=$(openssl rand -hex 32)

# -----------------------------------------------------------------------
# SETUP DIRECTORIES & REPOSITORY
# -----------------------------------------------------------------------
log_section "DIRECTORY & REPOSITORY SETUP"

if [[ -d "$DEPLOY_PATH" ]]; then
    log_warn "Directory $DEPLOY_PATH already exists."
    read -rp "  Continue with existing directory? (y/n): " _ans
    [[ "$_ans" =~ ^[Yy]$ ]] || exit 0
else
    mkdir -p "$DEPLOY_PATH"
    log_ok "Directory created: $DEPLOY_PATH"
fi

cd "$DEPLOY_PATH"

if [[ ! -d ".git" ]]; then
    read -rp "  Git repository URL: " REPO_URL
    [[ -z "$REPO_URL" ]] && die "Repository URL cannot be empty."
    git clone "$REPO_URL" .
    log_ok "Repository cloned"
else
    log_info "Repository exists — pulling latest changes..."
    git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || log_warn "git pull failed — continuing with current code"
    log_ok "Repository up to date"
fi

# -----------------------------------------------------------------------
# DETECT WAZUH ALERTS PATH
# -----------------------------------------------------------------------
log_section "WAZUH ALERTS PATH"

if [[ -d "/var/ossec/logs/alerts" ]]; then
    WAZUH_ALERTS_HOST_PATH="/var/ossec/logs/alerts"
    log_ok "Found Wazuh alerts directory: $WAZUH_ALERTS_HOST_PATH"
    chmod 755 /var/ossec/logs/alerts 2>/dev/null || true
    [[ -f "/var/ossec/logs/alerts/alerts.json" ]] && chmod 644 /var/ossec/logs/alerts/alerts.json 2>/dev/null || true
else
    log_warn "/var/ossec/logs/alerts not found — creating local stub directory"
    mkdir -p "$DEPLOY_PATH/data/wazuh"
    chmod 755 "$DEPLOY_PATH/data/wazuh"
    # Create stub alerts.json so the container can mount a real file
    touch "$DEPLOY_PATH/data/wazuh/alerts.json"
    WAZUH_ALERTS_HOST_PATH="$DEPLOY_PATH/data/wazuh"
fi

# -----------------------------------------------------------------------
# GENERATE .env.production
# NOTE: Use printf to avoid bash heredoc variable expansion issues.
#       All shell variables are expanded at write time — this is correct.
# -----------------------------------------------------------------------
log_section "GENERATING .env.production"

# Write env file using printf to avoid any heredoc quoting surprises
ENV_FILE="$DEPLOY_PATH/.env.production"

{
printf '# ================================================================\n'
printf '# MINI SOC PRODUCTION CONFIGURATION\n'
printf '# Generated by deploy_on_wazuh.sh on %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
printf '# ================================================================\n'
printf '\n'
printf '# ── Core ─────────────────────────────────────────────────────────\n'
printf 'PROJECT_NAME="Mini SOC Portal"\n'
printf 'ENV=production\n'
printf 'DEBUG=false\n'
printf 'API_V1_STR=/api/v1\n'
printf 'LOG_LEVEL=INFO\n'
printf '\n'
printf '# ── Security ─────────────────────────────────────────────────────\n'
printf 'SECRET_KEY=%s\n'                        "$SECRET_KEY"
printf 'ACCESS_TOKEN_EXPIRE_MINUTES=15\n'
printf 'REFRESH_TOKEN_EXPIRE_DAYS=7\n'
printf 'WS_TICKET_EXPIRE_SECONDS=60\n'
printf 'LOGIN_RATE_LIMIT_PER_MINUTE=10\n'
printf 'RATE_LIMIT_PER_MINUTE=100\n'
printf 'BACKEND_CORS_ORIGINS=http://%s:%s,http://localhost:%s\n'  "$SERVER_IP" "$NGINX_PORT" "$NGINX_PORT"
printf 'COOKIE_SECURE=false\n'
printf 'COOKIE_DOMAIN=\n'
printf 'CSRF_VALIDATE_ORIGIN=false\n'
printf '\n'
printf '# ── PostgreSQL ───────────────────────────────────────────────────\n'
printf 'POSTGRES_USER=postgres\n'
printf 'POSTGRES_PASSWORD=%s\n'                "$DB_PASSWORD"
printf 'POSTGRES_DB=mini_soc_prod\n'
printf 'POSTGRES_SERVER=db\n'
printf 'POSTGRES_PORT=5432\n'
printf 'DB_POOL_SIZE=20\n'
printf 'DB_MAX_OVERFLOW=40\n'
printf 'DB_POOL_TIMEOUT=30\n'
printf 'DB_POOL_RECYCLE=1800\n'
printf '\n'
printf '# ── Redis ────────────────────────────────────────────────────────\n'
printf 'REDIS_HOST=redis\n'
printf 'REDIS_PORT=6379\n'
printf 'REDIS_PASSWORD=%s\n'                   "$REDIS_PASSWORD"
printf 'REDIS_DB=0\n'
printf '\n'
printf '# ── Wazuh ────────────────────────────────────────────────────────\n'
printf 'WAZUH_API_URL=%s\n'                    "$WAZUH_API_URL"
printf 'WAZUH_API_USER=%s\n'                   "$WAZUH_API_USER"
printf 'WAZUH_API_PASSWORD=%s\n'               "$WAZUH_API_PASSWORD"
printf 'WAZUH_VERIFY_SSL=false\n'
printf 'WAZUH_ALERTS_FILE=/var/ossec/logs/alerts/alerts.json\n'
printf 'WAZUH_ALERTS_HOST_PATH=%s\n'           "$WAZUH_ALERTS_HOST_PATH"
printf '\n'
printf '# ── Zabbix ───────────────────────────────────────────────────────\n'
printf 'ZABBIX_API_URL=%s\n'                   "$ZABBIX_API_URL"
printf 'ZABBIX_API_USER=%s\n'                  "$ZABBIX_API_USER"
printf 'ZABBIX_API_PASSWORD=%s\n'              "$ZABBIX_API_PASSWORD"
printf 'ZABBIX_VERIFY_SSL=false\n'
printf 'ZABBIX_TIMEOUT=30\n'
printf 'ZABBIX_ENABLED=%s\n'                   "$ZABBIX_ENABLED"
printf '\n'
printf '# ── Frontend build-time URLs ─────────────────────────────────────\n'
printf 'VITE_API_URL=http://%s:%s/api/v1\n'   "$SERVER_IP" "$NGINX_PORT"
printf 'VITE_WS_URL=ws://%s:%s/ws\n'          "$SERVER_IP" "$NGINX_PORT"
printf '\n'
printf '# ── Nginx port ───────────────────────────────────────────────────\n'
printf 'NGINX_PORT=%s\n'                        "$NGINX_PORT"
printf '\n'
printf '# ── GeoIP / Observability ────────────────────────────────────────\n'
printf 'GEOIP_DB_PATH=/usr/share/GeoIP/GeoLite2-City.mmdb\n'
printf 'ENABLE_SENTRY=false\n'
printf 'SENTRY_DSN=\n'
printf '\n'
printf '# ── Default admin (first-boot fallback, NOT the interactive admin) ──\n'
printf 'DEFAULT_ADMIN_PASSWORD=%s\n'            "$ADMIN_PASSWORD"
} > "$ENV_FILE"

chmod 600 "$ENV_FILE"
log_ok ".env.production written (mode 600)"

# Verify critical keys
for KEY in POSTGRES_PASSWORD REDIS_PASSWORD SECRET_KEY WAZUH_API_PASSWORD; do
    grep -q "^${KEY}=" "$ENV_FILE" || die ".env.production is missing ${KEY}"
done
log_ok "All required variables present in .env.production"

# Load vars so they're available in this shell for subsequent docker commands
set -a; source "$ENV_FILE"; set +a

# -----------------------------------------------------------------------
# OPEN FIREWALL PORT (ufw — non-fatal if ufw not installed)
# -----------------------------------------------------------------------
log_section "FIREWALL CONFIGURATION"

if command -v ufw &>/dev/null; then
    ufw allow "${NGINX_PORT}/tcp" && ufw reload || log_warn "ufw rule failed — check firewall manually"
    log_ok "Firewall: port $NGINX_PORT/tcp opened"
else
    log_warn "ufw not found — make sure port $NGINX_PORT is reachable from outside"
fi

# -----------------------------------------------------------------------
# CLEAN UP OLD CONTAINERS (idempotent)
# -----------------------------------------------------------------------
log_section "CLEANING UP OLD CONTAINERS"

$DC -f docker-compose.production.yml --env-file "$ENV_FILE" down --remove-orphans 2>/dev/null || true
docker image prune -f --filter "dangling=true" 2>/dev/null || true
log_ok "Old containers removed"

# -----------------------------------------------------------------------
# BUILD IMAGES
# -----------------------------------------------------------------------
log_section "BUILDING DOCKER IMAGES"

# Validate compose config first
$DC -f docker-compose.production.yml --env-file "$ENV_FILE" config > /dev/null \
    || die "docker-compose config validation failed. Check .env.production."
log_ok "docker-compose config is valid"

log_info "Building backend image..."
$DC -f docker-compose.production.yml --env-file "$ENV_FILE" build backend \
    2>&1 | tee /tmp/soc_build_backend.log \
    || { log_error "Backend build failed:"; tail -40 /tmp/soc_build_backend.log; die "Aborting."; }
log_ok "Backend image built"

log_info "Building frontend image (bakes server URL at build time)..."
$DC -f docker-compose.production.yml --env-file "$ENV_FILE" build frontend \
    2>&1 | tee /tmp/soc_build_frontend.log \
    || { log_error "Frontend build failed:"; tail -40 /tmp/soc_build_frontend.log; die "Aborting."; }
log_ok "Frontend image built"

# -----------------------------------------------------------------------
# START DATABASE & REDIS FIRST
# -----------------------------------------------------------------------
log_section "STARTING DATABASE & REDIS"

$DC -f docker-compose.production.yml --env-file "$ENV_FILE" up -d db redis

log_info "Waiting for PostgreSQL (up to 120s)..."
DB_READY=false
for i in $(seq 1 60); do
    if $DC -f docker-compose.production.yml --env-file "$ENV_FILE" \
        exec -T db pg_isready -U postgres -d mini_soc_prod &>/dev/null; then
        log_ok "PostgreSQL is ready (attempt $i)"
        DB_READY=true
        break
    fi
    printf "."; sleep 2
done; echo ""
[[ "$DB_READY" == "true" ]] || { $DC -f docker-compose.production.yml logs db; die "PostgreSQL failed to start."; }

log_info "Waiting for Redis (up to 30s)..."
REDIS_READY=false
for i in $(seq 1 30); do
    if $DC -f docker-compose.production.yml --env-file "$ENV_FILE" \
        exec -T redis redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q "PONG"; then
        log_ok "Redis is ready (attempt $i)"
        REDIS_READY=true
        break
    fi
    printf "."; sleep 1
done; echo ""
[[ "$REDIS_READY" == "true" ]] || log_warn "Redis auth check failed — may still be starting. Continuing..."

# -----------------------------------------------------------------------
# DATABASE MIGRATIONS
# NOTE: Pass ALL env vars that app/core/config.py (Settings) requires so
#       Alembic can build the DB URL via SQLALCHEMY_DATABASE_URI.
# -----------------------------------------------------------------------
log_section "RUNNING DATABASE MIGRATIONS"

$DC -f docker-compose.production.yml --env-file "$ENV_FILE" run --rm \
    -e ENV=production \
    -e DEBUG=false \
    -e POSTGRES_SERVER=db \
    -e POSTGRES_PORT=5432 \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD="$DB_PASSWORD" \
    -e POSTGRES_DB=mini_soc_prod \
    -e SECRET_KEY="$SECRET_KEY" \
    -e REDIS_HOST=redis \
    -e REDIS_PORT=6379 \
    -e REDIS_PASSWORD="$REDIS_PASSWORD" \
    -e REDIS_DB=0 \
    -e WAZUH_API_URL="$WAZUH_API_URL" \
    -e WAZUH_API_USER="$WAZUH_API_USER" \
    -e WAZUH_API_PASSWORD="$WAZUH_API_PASSWORD" \
    -e ZABBIX_API_URL="$ZABBIX_API_URL" \
    -e ZABBIX_API_USER="$ZABBIX_API_USER" \
    -e ZABBIX_API_PASSWORD="$ZABBIX_API_PASSWORD" \
    -e ZABBIX_ENABLED="$ZABBIX_ENABLED" \
    backend \
    sh -c "cd /app && alembic upgrade head" \
    2>&1 | tee /tmp/soc_migration.log \
    || { log_error "Migration failed:"; cat /tmp/soc_migration.log; \
         $DC -f docker-compose.production.yml logs db; die "Aborting."; }
log_ok "Migrations applied successfully"

# -----------------------------------------------------------------------
# START ALL SERVICES
# -----------------------------------------------------------------------
log_section "STARTING ALL SERVICES"

$DC -f docker-compose.production.yml --env-file "$ENV_FILE" up -d

# Wait for backend health
log_info "Waiting for backend to become healthy (up to 120s)..."
BACKEND_READY=false
for i in $(seq 1 60); do
    if curl -sf "http://localhost:8000/api/v1/health/ready" > /dev/null 2>&1; then
        log_ok "Backend healthy (attempt $i)"
        BACKEND_READY=true
        break
    fi
    printf "."; sleep 2
done; echo ""
if [[ "$BACKEND_READY" != "true" ]]; then
    log_warn "Backend not reachable on localhost:8000 directly — trying via Nginx..."
fi

# Wait for Nginx (the public-facing port)
log_info "Waiting for Nginx on port $NGINX_PORT (up to 60s)..."
NGINX_READY=false
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${NGINX_PORT}/api/v1/health/ready" > /dev/null 2>&1; then
        log_ok "Nginx is serving (attempt $i)"
        NGINX_READY=true
        BACKEND_READY=true  # If Nginx passes, backend is reachable
        break
    fi
    printf "."; sleep 2
done; echo ""

if [[ "$BACKEND_READY" != "true" ]]; then
    $DC -f docker-compose.production.yml --env-file "$ENV_FILE" logs --tail=80 backend
    die "Backend failed to become healthy. Check logs above."
fi

[[ "$NGINX_READY" == "true" ]] || log_warn "Nginx not responding yet — may still be starting."

# -----------------------------------------------------------------------
# CREATE ADMIN USER
# NOTE: Script is at /app/app/scripts/create_admin_user.py inside container
#       (backend context = ./backend, WORKDIR = /app, so code is at /app/app/...)
# -----------------------------------------------------------------------
log_section "CREATING ADMIN USER"

if $DC -f docker-compose.production.yml --env-file "$ENV_FILE" exec -T backend \
    python /app/app/scripts/create_admin_user.py \
    --email "$ADMIN_EMAIL" \
    --password "$ADMIN_PASSWORD" \
    --user "$ADMIN_USER" \
    2>&1 | tee /tmp/soc_admin.log; then
    log_ok "Admin user created/verified: $ADMIN_EMAIL"
else
    EXIT_CODE=${PIPESTATUS[0]}
    log_warn "Admin creation exited with code $EXIT_CODE (may already exist — see below)"
    cat /tmp/soc_admin.log
    # Non-fatal: if admin already exists that's fine
fi

# -----------------------------------------------------------------------
# POST-DEPLOYMENT VALIDATION
# -----------------------------------------------------------------------
log_section "POST-DEPLOYMENT VALIDATION"

FAIL=0

# 1. Containers
log_info "[1/6] Container status..."
RUNNING=$($DC -f docker-compose.production.yml --env-file "$ENV_FILE" ps --services --filter "status=running" 2>/dev/null | wc -l)
EXPECTED=5   # db, redis, backend, frontend, nginx
if [[ "$RUNNING" -ge "$EXPECTED" ]]; then
    log_ok "All $RUNNING containers running"
else
    log_error "Only $RUNNING/$EXPECTED containers running!"
    $DC -f docker-compose.production.yml --env-file "$ENV_FILE" ps
    FAIL=1
fi

# 2. PostgreSQL
log_info "[2/6] PostgreSQL connectivity..."
if $DC -f docker-compose.production.yml --env-file "$ENV_FILE" exec -T db \
    pg_isready -U postgres -d mini_soc_prod &>/dev/null; then
    log_ok "PostgreSQL accessible"
else
    log_error "PostgreSQL not accessible!"; FAIL=1
fi

# 3. Migration version (dynamic — does not hardcode a specific version)
log_info "[3/6] Migration version..."
MIG_VER=$($DC -f docker-compose.production.yml --env-file "$ENV_FILE" exec -T db \
    psql -U postgres -d mini_soc_prod -tAc \
    "SELECT version_num FROM alembic_version ORDER BY 1 DESC LIMIT 1;" 2>/dev/null || echo "none")
MIG_VER=$(echo "$MIG_VER" | tr -d '[:space:]')
if [[ "$MIG_VER" != "none" && -n "$MIG_VER" ]]; then
    log_ok "Migration applied: $MIG_VER"
else
    log_error "No migration detected!"; FAIL=1
fi

# 4. Redis
log_info "[4/6] Redis..."
if $DC -f docker-compose.production.yml --env-file "$ENV_FILE" exec -T redis \
    redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q "PONG"; then
    log_ok "Redis accessible"
else
    log_warn "Redis ping failed — may still be starting"
fi

# 5. Backend health (via Nginx)
log_info "[5/6] Backend API via Nginx..."
HEALTH=$(curl -sf "http://localhost:${NGINX_PORT}/api/v1/health/ready" 2>/dev/null || echo "")
if echo "$HEALTH" | grep -qi "ok\|healthy\|ready"; then
    log_ok "Backend health check passed"
else
    log_error "Backend health check failed (response: ${HEALTH:-<empty>})"; FAIL=1
fi

# 6. Frontend
log_info "[6/6] Frontend..."
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:${NGINX_PORT}/" 2>/dev/null || echo "000")
if [[ "$HTTP_CODE" == "200" ]]; then
    log_ok "Frontend accessible (HTTP 200)"
else
    log_error "Frontend returned HTTP $HTTP_CODE"; FAIL=1
fi

# -----------------------------------------------------------------------
# SAVE DEPLOYMENT INFO (mode 600 — owner only)
# -----------------------------------------------------------------------
INFO_FILE="$DEPLOY_PATH/DEPLOYMENT_INFO.txt"
{
printf 'Mini-SOC Deployment Information\n'
printf 'Generated : %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
printf '==========================================================\n\n'
printf 'Access URL      : http://%s:%s\n'   "$SERVER_IP"   "$NGINX_PORT"
printf 'Deployment Path : %s\n'             "$DEPLOY_PATH"
printf 'Nginx Port      : %s\n'             "$NGINX_PORT"
printf 'Server IP       : %s\n'             "$SERVER_IP"
printf '\n'
printf 'Admin Email     : %s\n'             "$ADMIN_EMAIL"
printf 'Admin Username  : %s\n'             "$ADMIN_USER"
printf '\n'
printf 'Wazuh API       : %s\n'             "$WAZUH_API_URL"
printf 'Wazuh User      : %s\n'             "$WAZUH_API_USER"
printf 'Zabbix Enabled  : %s\n'             "$ZABBIX_ENABLED"
printf 'Zabbix URL      : %s\n'             "${ZABBIX_API_URL:-N/A}"
printf '\n'
printf '==========================================================\n'
printf 'SENSITIVE — STORE SECURELY\n'
printf 'DB Password     : %s\n'             "$DB_PASSWORD"
printf 'Redis Password  : %s\n'             "$REDIS_PASSWORD"
printf 'Secret Key      : %s\n'             "$SECRET_KEY"
printf '==========================================================\n\n'
printf 'Migration       : %s\n'             "${MIG_VER:-unknown}"
printf 'Containers up   : %s\n'             "$RUNNING"
printf 'Validation      : %s\n'             "$([ "$FAIL" -eq 0 ] && echo 'PASSED' || echo 'FAILED')"
printf '\n'
$DC -f docker-compose.production.yml ps 2>/dev/null || true
} > "$INFO_FILE"
chmod 600 "$INFO_FILE"
log_ok "Deployment info saved to: $INFO_FILE"

# -----------------------------------------------------------------------
# SETUP SYSTEMD SERVICE FOR AUTO-START ON REBOOT
# -----------------------------------------------------------------------
log_section "SYSTEMD AUTO-START SERVICE"

SYSTEMD_SERVICE="/etc/systemd/system/mini-soc.service"
cat > "$SYSTEMD_SERVICE" <<SYSTEMD
[Unit]
Description=Mini-SOC Docker Compose Application
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${DEPLOY_PATH}
ExecStart=/usr/bin/env ${DC} -f docker-compose.production.yml --env-file ${ENV_FILE} up -d
ExecStop=/usr/bin/env ${DC} -f docker-compose.production.yml --env-file ${ENV_FILE} down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
SYSTEMD

# Resolve actual binary path for DC command (systemd needs full paths)
DC_BIN=$(command -v docker)
if [[ "$DC" == "docker compose" ]]; then
    EXEC_START="${DC_BIN} compose -f ${DEPLOY_PATH}/docker-compose.production.yml --env-file ${ENV_FILE} up -d"
    EXEC_STOP="${DC_BIN} compose -f ${DEPLOY_PATH}/docker-compose.production.yml --env-file ${ENV_FILE} down"
else
    DC_BIN=$(command -v docker-compose)
    EXEC_START="${DC_BIN} -f ${DEPLOY_PATH}/docker-compose.production.yml --env-file ${ENV_FILE} up -d"
    EXEC_STOP="${DC_BIN} -f ${DEPLOY_PATH}/docker-compose.production.yml --env-file ${ENV_FILE} down"
fi

cat > "$SYSTEMD_SERVICE" <<SYSTEMD
[Unit]
Description=Mini-SOC Docker Compose Application
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=${DEPLOY_PATH}
ExecStart=${EXEC_START}
ExecStop=${EXEC_STOP}
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
SYSTEMD

systemctl daemon-reload
systemctl enable mini-soc.service
log_ok "Systemd service installed and enabled (mini-soc.service)"
log_ok "Mini-SOC will auto-start on reboot"

# -----------------------------------------------------------------------
# FINAL SUMMARY
# -----------------------------------------------------------------------
echo ""
if [[ "$FAIL" -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║  ✅  DEPLOYMENT COMPLETED SUCCESSFULLY   ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${NC}"
else
    echo -e "${RED}${BOLD}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║  ⚠️   DEPLOYMENT FINISHED WITH WARNINGS  ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${NC}"
    log_warn "Review the errors above before using the system in production."
fi

echo ""
echo -e "${BOLD}📍 Access:${NC}"
echo "   Web UI     : http://$SERVER_IP:$NGINX_PORT"
echo "   Health     : http://$SERVER_IP:$NGINX_PORT/api/v1/health/ready"
echo ""
echo -e "${BOLD}👤 Admin:${NC}"
echo "   Email      : $ADMIN_EMAIL"
echo "   Username   : $ADMIN_USER"
echo "   Password   : (as entered — change on first login)"
echo ""
echo -e "${BOLD}🔧 Useful commands:${NC}"
echo "   Logs       : cd $DEPLOY_PATH && $DC -f docker-compose.production.yml logs -f backend"
echo "   Restart    : cd $DEPLOY_PATH && $DC -f docker-compose.production.yml restart"
echo "   Stop all   : cd $DEPLOY_PATH && $DC -f docker-compose.production.yml down"
echo "   DB backup  : $DC -f docker-compose.production.yml exec db pg_dump -U postgres mini_soc_prod > backup.sql"
echo ""
echo -e "${YELLOW}⚠ Security reminders:${NC}"
echo "   • Change admin password on first login"
echo "   • Keep $INFO_FILE safe — it contains secrets"
echo "   • Firewall port $NGINX_PORT has been opened (if ufw present)"
echo ""
