#!/bin/bash

#=============================================================================
# MINI-SOC API CONNECTIVITY DIAGNOSTIC TOOL
#=============================================================================
# Mục đích: Xác định chính xác nguyên nhân không nhận được dữ liệu:
#   - Wazuh API không hoạt động?
#   - Zabbix API không hoạt động?
#   - Hệ thống Mini-SOC có vấn đề?
#   - Cấu hình sai?
#=============================================================================

# NOTE: Don't use -e flag to allow script to continue on errors
set -uo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }
log_error() { echo -e "${RED}[✗]${NC} $1"; }
log_section() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN} $1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

#=============================================================================
# STEP 1: ĐỌC CÁC THÔNG TIN CẦN THIẾT
#=============================================================================

log_section "BƯỚC 1: Thu thập thông tin cấu hình"

# Check if running in Docker environment or host
if [ -f ".env.production" ]; then
    log_info "Đọc cấu hình từ .env.production..."
    source .env.production
    ENV_FILE=".env.production"
elif [ -f "backend/.env" ]; then
    log_info "Đọc cấu hình từ backend/.env..."
    source backend/.env
    ENV_FILE="backend/.env"
else
    log_error "Không tìm thấy file cấu hình (.env.production hoặc backend/.env)"
    exit 1
fi

log_success "Đã đọc cấu hình từ: $ENV_FILE"

# Display configuration
log_info "Cấu hình hiện tại:"
echo "  WAZUH_API_URL     : ${WAZUH_API_URL:-Not set}"
echo "  WAZUH_API_USER    : ${WAZUH_API_USER:-Not set}"
echo "  WAZUH_VERIFY_SSL  : ${WAZUH_VERIFY_SSL:-true}"
echo "  ZABBIX_API_URL    : ${ZABBIX_API_URL:-Not set}"
echo "  ZABBIX_API_USER   : ${ZABBIX_API_USER:-Not set}"
echo "  ZABBIX_ENABLED    : ${ZABBIX_ENABLED:-false}"

#=============================================================================
# STEP 2: KIỂM TRA WAZUH API
#=============================================================================

log_section "BƯỚC 2: Kiểm tra Wazuh API"

WAZUH_STATUS="UNKNOWN"
WAZUH_ERROR=""

if [ -z "${WAZUH_API_URL:-}" ]; then
    log_error "WAZUH_API_URL không được cấu hình"
    WAZUH_STATUS="NOT_CONFIGURED"
else
    log_info "Testing Wazuh API: $WAZUH_API_URL"
    
    # Extract host and port
    WAZUH_HOST=$(echo $WAZUH_API_URL | sed -e 's|^[^/]*//||' -e 's|:.*||')
    WAZUH_PORT=$(echo $WAZUH_API_URL | grep -oP ':\K[0-9]+' || echo "55000")
    
    log_info "Wazuh Host: $WAZUH_HOST"
    log_info "Wazuh Port: $WAZUH_PORT"
    
    # Test 1: Network connectivity
    log_info "Test 1: Network connectivity..."
    if ping -c 1 -W 2 "$WAZUH_HOST" &>/dev/null; then
        log_success "Host $WAZUH_HOST is reachable"
    else
        log_warning "Cannot ping $WAZUH_HOST (firewall may block ICMP)"
    fi
    
    # Test 2: Port connectivity
    log_info "Test 2: Port connectivity..."
    if timeout 5 bash -c "echo >/dev/tcp/$WAZUH_HOST/$WAZUH_PORT" 2>/dev/null; then
        log_success "Port $WAZUH_PORT is open on $WAZUH_HOST"
    else
        log_error "Cannot connect to port $WAZUH_PORT on $WAZUH_HOST"
        log_error "→ Wazuh API có thể không chạy hoặc firewall chặn"
        WAZUH_STATUS="PORT_CLOSED"
        WAZUH_ERROR="Port $WAZUH_PORT không mở hoặc firewall chặn"
    fi
    
    # Test 3: HTTPS/TLS connectivity
    if [ "$WAZUH_STATUS" != "PORT_CLOSED" ]; then
        log_info "Test 3: HTTPS/TLS connectivity..."
        
        # Prepare curl options
        CURL_OPTS="-s -o /dev/null -w %{http_code}"
        if [ "${WAZUH_VERIFY_SSL:-true}" = "false" ]; then
            CURL_OPTS="$CURL_OPTS -k"
        fi
        
        HTTP_CODE=$(curl $CURL_OPTS "$WAZUH_API_URL" 2>/dev/null || echo "000")
        
        if [ "$HTTP_CODE" = "000" ]; then
            log_error "Không thể kết nối HTTPS tới Wazuh API"
            log_error "→ SSL/TLS handshake failed hoặc service không chạy"
            WAZUH_STATUS="HTTPS_FAILED"
            WAZUH_ERROR="SSL/TLS connection failed"
        elif [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "200" ]; then
            log_success "Wazuh API responds (HTTP $HTTP_CODE)"
        else
            log_warning "Wazuh API returned HTTP $HTTP_CODE"
        fi
    fi
    
    # Test 4: Authentication
    if [ "$WAZUH_STATUS" != "PORT_CLOSED" ] && [ "$WAZUH_STATUS" != "HTTPS_FAILED" ]; then
        log_info "Test 4: Authentication..."
        
        if [ -z "${WAZUH_API_USER:-}" ] || [ -z "${WAZUH_API_PASSWORD:-}" ]; then
            log_error "WAZUH_API_USER hoặc WAZUH_API_PASSWORD không được set"
            WAZUH_STATUS="NO_CREDENTIALS"
            WAZUH_ERROR="Missing credentials"
        else
            CURL_OPTS="-s"
            if [ "${WAZUH_VERIFY_SSL:-true}" = "false" ]; then
                CURL_OPTS="$CURL_OPTS -k"
            fi
            
            # Try to authenticate
            AUTH_RESPONSE=$(curl $CURL_OPTS -u "${WAZUH_API_USER}:${WAZUH_API_PASSWORD}" \
                -X GET "${WAZUH_API_URL}/security/user/authenticate" 2>&1 || echo "CURL_FAILED")
            
            if echo "$AUTH_RESPONSE" | grep -q "token" 2>/dev/null || false; then
                log_success "Wazuh authentication successful"
                WAZUH_TOKEN=$(echo "$AUTH_RESPONSE" | grep -o '"token":"[^"]*"' | cut -d'"' -f4 || echo "")
                log_info "Received token: ${WAZUH_TOKEN:0:20}..."
                WAZUH_STATUS="OK"
                
                # Test 5: Get agents
                log_info "Test 5: Fetching agents list..."
                AGENTS_RESPONSE=$(curl $CURL_OPTS -H "Authorization: Bearer $WAZUH_TOKEN" \
                    -X GET "${WAZUH_API_URL}/agents?limit=5" 2>&1 || echo "CURL_FAILED")
                
                if echo "$AGENTS_RESPONSE" | grep -q "affected_items" 2>/dev/null || false; then
                    AGENT_COUNT=$(echo "$AGENTS_RESPONSE" | grep -o '"total_affected_items":[0-9]*' | cut -d':' -f2 || echo "0")
                    log_success "Wazuh API trả về danh sách agents: $AGENT_COUNT agents"
                else
                    log_warning "Wazuh API không trả về agents list"
                    log_info "Response: ${AGENTS_RESPONSE:0:200}"
                fi
                
            else
                log_error "Wazuh authentication failed"
                log_error "Response: ${AUTH_RESPONSE:0:200}"
                
                if echo "$AUTH_RESPONSE" | grep -qi "invalid credentials" 2>/dev/null || false; then
                    WAZUH_STATUS="INVALID_CREDENTIALS"
                    WAZUH_ERROR="Username hoặc password sai"
                elif echo "$AUTH_RESPONSE" | grep -qi "Connection refused" 2>/dev/null || false; then
                    WAZUH_STATUS="CONNECTION_REFUSED"
                    WAZUH_ERROR="Wazuh service không chạy"
                else
                    WAZUH_STATUS="AUTH_FAILED"
                    WAZUH_ERROR="Authentication failed: ${AUTH_RESPONSE:0:100}"
                fi
            fi
        fi
    fi
fi

#=============================================================================
# STEP 3: KIỂM TRA ZABBIX API
#=============================================================================

log_section "BƯỚC 3: Kiểm tra Zabbix API"

ZABBIX_STATUS="UNKNOWN"
ZABBIX_ERROR=""

if [ "${ZABBIX_ENABLED:-false}" != "true" ]; then
    log_warning "Zabbix không được enable trong cấu hình"
    ZABBIX_STATUS="DISABLED"
elif [ -z "${ZABBIX_API_URL:-}" ]; then
    log_error "ZABBIX_API_URL không được cấu hình"
    ZABBIX_STATUS="NOT_CONFIGURED"
else
    log_info "Testing Zabbix API: $ZABBIX_API_URL"
    
    # Extract host
    ZABBIX_HOST=$(echo $ZABBIX_API_URL | sed -e 's|^[^/]*//||' -e 's|/.*||')
    log_info "Zabbix Host: $ZABBIX_HOST"
    
    # Test 1: HTTP connectivity
    log_info "Test 1: HTTP connectivity..."
    HTTP_CODE=$(curl -s -o /dev/null -w %{http_code} "$ZABBIX_API_URL" 2>/dev/null || echo "000")
    
    if [ "$HTTP_CODE" = "000" ]; then
        log_error "Cannot connect to Zabbix API"
        ZABBIX_STATUS="CONNECTION_FAILED"
        ZABBIX_ERROR="Cannot reach $ZABBIX_API_URL"
    elif [ "$HTTP_CODE" = "200" ]; then
        log_success "Zabbix API endpoint accessible (HTTP $HTTP_CODE)"
        
        # Test 2: API authentication
        log_info "Test 2: API authentication..."
        
        if [ -z "${ZABBIX_API_USER:-}" ] || [ -z "${ZABBIX_API_PASSWORD:-}" ]; then
            log_error "ZABBIX_API_USER hoặc ZABBIX_API_PASSWORD không được set"
            ZABBIX_STATUS="NO_CREDENTIALS"
            ZABBIX_ERROR="Missing credentials"
        else
            AUTH_PAYLOAD=$(cat <<EOF
{
    "jsonrpc": "2.0",
    "method": "user.login",
    "params": {
        "user": "${ZABBIX_API_USER}",
        "password": "${ZABBIX_API_PASSWORD}"
    },
    "id": 1
}
EOF
)
            
            AUTH_RESPONSE=$(curl -s -X POST "$ZABBIX_API_URL" \
                -H "Content-Type: application/json-rpc" \
                -d "$AUTH_PAYLOAD" 2>&1 || echo "CURL_FAILED")
            
            if echo "$AUTH_RESPONSE" | grep -q '"result"' 2>/dev/null || false; then
                log_success "Zabbix authentication successful"
                ZABBIX_TOKEN=$(echo "$AUTH_RESPONSE" | grep -o '"result":"[^"]*"' | cut -d'"' -f4 || echo "")
                log_info "Received token: ${ZABBIX_TOKEN:0:20}..."
                ZABBIX_STATUS="OK"
                
                # Test 3: Get hosts
                log_info "Test 3: Fetching hosts list..."
                HOSTS_PAYLOAD=$(cat <<EOF
{
    "jsonrpc": "2.0",
    "method": "host.get",
    "params": {
        "output": ["hostid", "host"],
        "limit": 5
    },
    "auth": "$ZABBIX_TOKEN",
    "id": 2
}
EOF
)
                
                HOSTS_RESPONSE=$(curl -s -X POST "$ZABBIX_API_URL" \
                    -H "Content-Type: application/json-rpc" \
                    -d "$HOSTS_PAYLOAD" 2>&1 || echo "CURL_FAILED")
                
                if echo "$HOSTS_RESPONSE" | grep -q '"result"' 2>/dev/null || false; then
                    HOST_COUNT=$(echo "$HOSTS_RESPONSE" | grep -o '"hostid"' | wc -l || echo "0")
                    log_success "Zabbix API trả về danh sách hosts: $HOST_COUNT hosts"
                else
                    log_warning "Zabbix API không trả về hosts list"
                fi
                
            else
                log_error "Zabbix authentication failed"
                log_error "Response: ${AUTH_RESPONSE:0:200}"
                
                if echo "$AUTH_RESPONSE" | grep -qi "incorrect.*password" 2>/dev/null || false; then
                    ZABBIX_STATUS="INVALID_CREDENTIALS"
                    ZABBIX_ERROR="Username hoặc password sai"
                else
                    ZABBIX_STATUS="AUTH_FAILED"
                    ZABBIX_ERROR="Authentication failed"
                fi
            fi
        fi
    else
        log_warning "Zabbix API returned HTTP $HTTP_CODE"
        ZABBIX_STATUS="HTTP_ERROR"
        ZABBIX_ERROR="HTTP $HTTP_CODE"
    fi
fi

#=============================================================================
# STEP 4: KIỂM TRA MINI-SOC BACKEND
#=============================================================================

log_section "BƯỚC 4: Kiểm tra Mini-SOC Backend"

BACKEND_STATUS="UNKNOWN"

# Check if backend container is running
BACKEND_CONTAINER=$(docker ps --filter "name=backend" --format "{{.Names}}" 2>/dev/null | head -1 || echo "")

if [ -n "$BACKEND_CONTAINER" ]; then
    log_success "Backend container đang chạy: $BACKEND_CONTAINER"
    
    # Check logs for Wazuh connection errors
    log_info "Kiểm tra logs cho lỗi Wazuh connection..."
    WAZUH_ERRORS=$(docker logs "$BACKEND_CONTAINER" 2>&1 | \
        grep -i "wazuh" | grep -iE "error|failed|refused|timeout" | tail -5 || echo "")
    
    if [ -n "$WAZUH_ERRORS" ]; then
        log_warning "Phát hiện lỗi Wazuh trong backend logs:"
        echo "$WAZUH_ERRORS" | while read line; do
            echo "    $line"
        done
    else
        log_info "Không có lỗi Wazuh connection trong logs gần đây"
    fi
    
    # Check for Zabbix errors
    if [ "${ZABBIX_ENABLED:-false}" = "true" ]; then
        log_info "Kiểm tra logs cho lỗi Zabbix connection..."
        ZABBIX_ERRORS=$(docker logs "$BACKEND_CONTAINER" 2>&1 | \
            grep -i "zabbix" | grep -iE "error|failed|refused|timeout" | tail -5 || echo "")
        
        if [ -n "$ZABBIX_ERRORS" ]; then
            log_warning "Phát hiện lỗi Zabbix trong backend logs:"
            echo "$ZABBIX_ERRORS" | while read line; do
                echo "    $line"
            done
        else
            log_info "Không có lỗi Zabbix connection trong logs gần đây"
        fi
    fi
    
    # Check collector status
    log_info "Kiểm tra collector status..."
    COLLECTOR_LOGS=$(docker logs "$BACKEND_CONTAINER" 2>&1 | \
        grep "collector" | tail -10 || echo "")
    
    if echo "$COLLECTOR_LOGS" | grep -q "collector_starting" 2>/dev/null || false; then
        log_success "Collector đã khởi động"
    else
        log_warning "Không thấy collector startup message"
    fi
    
    if echo "$COLLECTOR_LOGS" | grep -q "collector_stats" 2>/dev/null || false; then
        log_success "Collector đang hoạt động (có stats)"
        LAST_STATS=$(echo "$COLLECTOR_LOGS" | grep "collector_stats" | tail -1 || echo "")
        log_info "Last stats: $LAST_STATS"
    else
        log_warning "Collector chưa có stats (chưa xử lý events)"
    fi
    
    BACKEND_STATUS="RUNNING"
else
    log_error "Backend container KHÔNG chạy"
    BACKEND_STATUS="NOT_RUNNING"
fi

#=============================================================================
# STEP 5: KIỂM TRA DATABASE
#=============================================================================

log_section "BƯỚC 5: Kiểm tra Database"

DB_CONTAINER=$(docker ps --filter "name=db" --format "{{.Names}}" 2>/dev/null | head -1 || echo "")
WAZUH_EVENTS="0"
AGENTS="0"

if [ -n "$DB_CONTAINER" ]; then
    log_success "Database container đang chạy: $DB_CONTAINER"
    
    # Check for wazuh_events
    log_info "Kiểm tra dữ liệu trong database..."
    
    # Count wazuh events
    WAZUH_EVENTS=$(docker exec "$DB_CONTAINER" psql -U postgres -d "${POSTGRES_DB:-mini_soc_prod}" \
        -tAc "SELECT COUNT(*) FROM wazuh_events;" 2>/dev/null || echo "0")
    
    log_info "Wazuh events trong database: $WAZUH_EVENTS"
    
    if [ "$WAZUH_EVENTS" -gt 0 ] 2>/dev/null; then
        log_success "Database có $WAZUH_EVENTS wazuh events"
        
        # Show latest event
        LATEST_EVENT=$(docker exec "$DB_CONTAINER" psql -U postgres -d "${POSTGRES_DB:-mini_soc_prod}" \
            -c "SELECT event_timestamp, severity, agent_name FROM wazuh_events ORDER BY event_timestamp DESC LIMIT 1;" 2>/dev/null || echo "")
        if [ -n "$LATEST_EVENT" ]; then
            log_info "Event mới nhất:"
            echo "$LATEST_EVENT"
        fi
    else
        log_warning "Database KHÔNG CÓ wazuh events"
        log_warning "→ Collector chưa thu thập được dữ liệu từ Wazuh"
    fi
    
    # Check endpoint_inventory
    AGENTS=$(docker exec "$DB_CONTAINER" psql -U postgres -d "${POSTGRES_DB:-mini_soc_prod}" \
        -tAc "SELECT COUNT(*) FROM endpoint_inventory;" 2>/dev/null || echo "0")
    
    log_info "Agents trong endpoint_inventory: $AGENTS"
    
    if [ "$AGENTS" -gt 0 ] 2>/dev/null; then
        log_success "Database có $AGENTS agents"
    else
        log_warning "Database KHÔNG CÓ agents"
        log_warning "→ Agent sync chưa chạy hoặc Wazuh API không trả về agents"
    fi
    
else
    log_error "Database container KHÔNG chạy"
fi

#=============================================================================
# STEP 6: KIỂM TRA WAZUH ALERTS FILE
#=============================================================================

log_section "BƯỚC 6: Kiểm tra Wazuh Alerts File"

if [ -n "$BACKEND_CONTAINER" ]; then
    log_info "Kiểm tra alerts file trong backend container..."
    
    if docker exec "$BACKEND_CONTAINER" test -f /var/ossec/logs/alerts/alerts.json 2>/dev/null; then
        log_success "Alerts file tồn tại: /var/ossec/logs/alerts/alerts.json"
        
        # Check file size
        FILE_SIZE=$(docker exec "$BACKEND_CONTAINER" stat -c%s /var/ossec/logs/alerts/alerts.json 2>/dev/null || echo "0")
        log_info "File size: $FILE_SIZE bytes"
        
        if [ "$FILE_SIZE" -gt 0 ] 2>/dev/null; then
            log_success "Alerts file có dữ liệu"
            
            # Show last line
            log_info "Dòng cuối cùng trong alerts file:"
            docker exec "$BACKEND_CONTAINER" tail -n 1 /var/ossec/logs/alerts/alerts.json 2>/dev/null || log_warning "Không đọc được file"
        else
            log_warning "Alerts file RỖNG (0 bytes)"
            log_warning "→ Wazuh chưa tạo ra alerts"
        fi
    else
        log_error "Alerts file KHÔNG TỒN TẠI trong container"
        log_error "→ Volume mount có vấn đề hoặc Wazuh chưa cài đặt"
        
        # Check volume mounts
        log_info "Volume mounts của backend container:"
        docker inspect "$BACKEND_CONTAINER" --format '{{json .Mounts}}' 2>/dev/null | \
            jq -r '.[] | select(.Destination == "/var/ossec/logs/alerts") | "Source: \(.Source)\nDestination: \(.Destination)\nMode: \(.Mode)"' 2>/dev/null || \
            log_warning "Không thể lấy thông tin volume mounts (jq có thể chưa cài)"
    fi
else
    log_warning "Backend container không chạy, bỏ qua kiểm tra alerts file"
fi

#=============================================================================
# STEP 7: TẠO BÁO CÁO
#=============================================================================

log_section "BÁO CÁO CHẨN ĐOÁN"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              DIAGNOSTIC SUMMARY                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Wazuh Status
echo "1. WAZUH API"
echo "   Status: $WAZUH_STATUS"
if [ "$WAZUH_STATUS" = "OK" ]; then
    echo -e "   ${GREEN}✓ Wazuh API hoạt động bình thường${NC}"
    echo "   → Mini-SOC CÓ THỂ kết nối với Wazuh"
elif [ "$WAZUH_STATUS" = "NOT_CONFIGURED" ]; then
    echo -e "   ${RED}✗ Wazuh API chưa được cấu hình${NC}"
    echo "   → Cần cấu hình WAZUH_API_URL trong .env"
elif [ "$WAZUH_STATUS" = "PORT_CLOSED" ]; then
    echo -e "   ${RED}✗ Wazuh API port không mở${NC}"
    echo "   → Wazuh service KHÔNG CHẠY hoặc firewall chặn"
    echo "   Error: $WAZUH_ERROR"
elif [ "$WAZUH_STATUS" = "INVALID_CREDENTIALS" ]; then
    echo -e "   ${RED}✗ Credentials sai${NC}"
    echo "   → Kiểm tra WAZUH_API_USER và WAZUH_API_PASSWORD"
else
    echo -e "   ${RED}✗ Wazuh API không hoạt động${NC}"
    echo "   Error: $WAZUH_ERROR"
fi
echo ""

# Zabbix Status
echo "2. ZABBIX API"
echo "   Status: $ZABBIX_STATUS"
if [ "$ZABBIX_STATUS" = "OK" ]; then
    echo -e "   ${GREEN}✓ Zabbix API hoạt động bình thường${NC}"
elif [ "$ZABBIX_STATUS" = "DISABLED" ]; then
    echo -e "   ${YELLOW}⚠ Zabbix bị disable${NC}"
    echo "   → Nếu muốn dùng, set ZABBIX_ENABLED=true"
elif [ "$ZABBIX_STATUS" = "NOT_CONFIGURED" ]; then
    echo -e "   ${YELLOW}⚠ Zabbix API chưa được cấu hình${NC}"
else
    echo -e "   ${RED}✗ Zabbix API không hoạt động${NC}"
    echo "   Error: $ZABBIX_ERROR"
fi
echo ""

# Backend Status
echo "3. MINI-SOC BACKEND"
echo "   Status: $BACKEND_STATUS"
if [ "$BACKEND_STATUS" = "RUNNING" ]; then
    echo -e "   ${GREEN}✓ Backend đang chạy${NC}"
else
    echo -e "   ${RED}✗ Backend không chạy${NC}"
fi
echo ""

# Database Status
echo "4. DATABASE"
if [ "${WAZUH_EVENTS:-0}" -gt 0 ] 2>/dev/null; then
    echo -e "   ${GREEN}✓ Có $WAZUH_EVENTS wazuh events${NC}"
    echo "   → Hệ thống ĐÃ thu thập được dữ liệu"
else
    echo -e "   ${RED}✗ Không có wazuh events${NC}"
    echo "   → Collector chưa thu thập được dữ liệu"
fi

if [ "${AGENTS:-0}" -gt 0 ] 2>/dev/null; then
    echo -e "   ${GREEN}✓ Có $AGENTS agents${NC}"
else
    echo -e "   ${YELLOW}⚠ Không có agents${NC}"
fi
echo ""

#=============================================================================
# KẾT LUẬN
#=============================================================================

echo "╔════════════════════════════════════════════════════════════╗"
echo "║              KẾT LUẬN                                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if [ "$WAZUH_STATUS" = "OK" ] && [ "${WAZUH_EVENTS:-0}" -gt 0 ] 2>/dev/null; then
    echo -e "${GREEN}✓ HỆ THỐNG HOẠT ĐỘNG BÌNH THƯỜNG${NC}"
    echo ""
    echo "Wazuh API hoạt động và hệ thống đã thu thập $WAZUH_EVENTS events."
    echo "Dashboard sẽ hiển thị dữ liệu."
    
elif [ "$WAZUH_STATUS" != "OK" ]; then
    echo -e "${RED}✗ LỖI TỪ WAZUH API${NC}"
    echo ""
    echo "NGUYÊN NHÂN: Wazuh API không hoạt động"
    echo "LỖI: $WAZUH_ERROR"
    echo ""
    echo "GIẢI PHÁP:"
    
    if [ "$WAZUH_STATUS" = "PORT_CLOSED" ]; then
        echo "  1. Kiểm tra Wazuh service: systemctl status wazuh-manager"
        echo "  2. Start Wazuh nếu chưa chạy: systemctl start wazuh-manager"
        echo "  3. Kiểm tra firewall: ufw status"
    elif [ "$WAZUH_STATUS" = "INVALID_CREDENTIALS" ]; then
        echo "  1. Kiểm tra credentials trong .env.production"
        echo "  2. Lấy password đúng từ Wazuh:"
        echo "     cat /var/ossec/.secret"
        echo "  3. Hoặc reset password trong Wazuh dashboard"
    elif [ "$WAZUH_STATUS" = "NOT_CONFIGURED" ]; then
        echo "  1. Cấu hình WAZUH_API_URL trong .env.production"
        echo "  2. Format: https://<IP>:55000"
        echo "  3. Restart containers"
    fi
    
elif [ "${WAZUH_EVENTS:-0}" -eq 0 ] 2>/dev/null; then
    echo -e "${YELLOW}⚠ WAZUH API HOẠT ĐỘNG NHƯNG CHƯA CÓ DỮ LIỆU${NC}"
    echo ""
    echo "NGUYÊN NHÂN:"
    echo "  - Wazuh API hoạt động tốt"
    echo "  - Nhưng chưa có alerts trong database"
    echo ""
    echo "CÓ THỂ DO:"
    echo "  1. Wazuh alerts file trống (Wazuh chưa tạo alerts)"
    echo "  2. Volume mount không đúng"
    echo "  3. Collector chưa xử lý alerts"
    echo ""
    echo "GIẢI PHÁP:"
    echo "  1. Inject test data để test UI:"
    echo "     bash inject_test_data.sh"
    echo "  2. Kiểm tra Wazuh có agents kết nối:"
    echo "     /var/ossec/bin/agent_control -l"
    echo "  3. Kiểm tra Wazuh alerts file:"
    echo "     tail -f /var/ossec/logs/alerts/alerts.json"
fi

echo ""
echo "Để xem log chi tiết:"
echo "  docker logs <container-name> --tail 100"
echo ""

# Save report
REPORT_FILE="api_diagnostic_$(date +%Y%m%d_%H%M%S).txt"
{
    echo "MINI-SOC API Diagnostic Report"
    echo "Generated: $(date)"
    echo ""
    echo "WAZUH API Status: $WAZUH_STATUS"
    echo "ZABBIX API Status: $ZABBIX_STATUS"
    echo "Backend Status: $BACKEND_STATUS"
    echo "Wazuh Events: $WAZUH_EVENTS"
    echo "Agents: $AGENTS"
} > "$REPORT_FILE"

log_success "Báo cáo đã lưu: $REPORT_FILE"
