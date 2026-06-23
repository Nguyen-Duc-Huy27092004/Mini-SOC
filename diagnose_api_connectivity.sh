#!/bin/bash

#=============================================================================
# MINI-SOC API CONNECTIVITY DIAGNOSTIC TOOL  (v2 – chi tiết lỗi + fix)
#=============================================================================
# Mục đích: Xác định CHÍNH XÁC nguyên nhân lỗi kết nối API và đưa ra
#           hướng dẫn khắc phục cụ thể cho:
#   - Wazuh API  (port 55000, Basic-Auth → JWT)
#   - Zabbix API (JSON-RPC, hỗ trợ cả session-token lẫn API-token)
#   - Mini-SOC Backend + Database
#=============================================================================

# NOTE: Không dùng -e để script tiếp tục chạy khi gặp lỗi
set -uo pipefail

# ── Colors ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[⚠]${NC} $1"; }
log_error()   { echo -e "${RED}[✗]${NC} $1"; }
log_fix()     { echo -e "${MAGENTA}[FIX]${NC} $1"; }
log_detail()  { echo -e "      ${WHITE}↳${NC} $1"; }
log_section() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
}

# ── Giải thích curl exit code ────────────────────────────────────────────────
explain_curl_exit() {
    local code=$1
    case "$code" in
        1)  echo "Unsupported protocol – URL scheme không được hỗ trợ" ;;
        3)  echo "URL malformed – URL không hợp lệ, kiểm tra ZABBIX_API_URL / WAZUH_API_URL" ;;
        5)  echo "Couldn't resolve proxy – proxy không phân giải được" ;;
        6)  echo "Couldn't resolve host – DNS không phân giải được hostname" ;;
        7)  echo "Failed to connect – cổng đóng hoặc service không chạy" ;;
        28) echo "Operation timed out – server không phản hồi (timeout)" ;;
        35) echo "SSL connect error – TLS handshake thất bại (cert sai / SSL version mismatch)" ;;
        51) echo "SSL peer cert verification failed – cert không hợp lệ hoặc tự ký" ;;
        52) echo "Server returned nothing – server chấp nhận kết nối nhưng không gửi response" ;;
        56) echo "Recv failure – kết nối bị reset bởi server" ;;
        60) echo "SSL CA cert problem – CA cert không được tin cậy, thử -k hoặc thêm cert" ;;
        *)  echo "curl error $code – xem: man curl (ERRORS section)" ;;
    esac
}

# ── Helper: chạy curl và trả về HTTP code + body + exit code ────────────────
# Usage: run_curl <label> <curl_args...>
# Sets globals: CURL_HTTP_CODE  CURL_BODY  CURL_EXIT  CURL_VERBOSE
run_curl_full() {
    local label="$1"; shift
    local tmp_body tmp_verbose tmp_code
    tmp_body=$(mktemp)
    tmp_verbose=$(mktemp)

    # Chạy curl: lưu body, verbose vào file riêng
    curl --max-time 15 --connect-timeout 8 \
         -o "$tmp_body" \
         -w "%{http_code}" \
         -v \
         "$@" 2>"$tmp_verbose"
    CURL_EXIT=$?
    CURL_HTTP_CODE=$(curl --max-time 15 --connect-timeout 8 \
         -o /dev/null -w "%{http_code}" \
         "$@" 2>/dev/null) || CURL_HTTP_CODE="000"

    CURL_BODY=$(cat "$tmp_body" 2>/dev/null || echo "")
    CURL_VERBOSE=$(cat "$tmp_verbose" 2>/dev/null || echo "")
    rm -f "$tmp_body" "$tmp_verbose"

    log_detail "curl exit=$CURL_EXIT  http=$CURL_HTTP_CODE  label=$label"
}

#=============================================================================
# BƯỚC 1: ĐỌC CẤU HÌNH
#=============================================================================
log_section "BƯỚC 1: Thu thập thông tin cấu hình"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if   [ -f "$SCRIPT_DIR/.env.production" ]; then
    ENV_FILE="$SCRIPT_DIR/.env.production"
elif [ -f "$SCRIPT_DIR/backend/.env" ]; then
    ENV_FILE="$SCRIPT_DIR/backend/.env"
elif [ -f ".env.production" ]; then
    ENV_FILE=".env.production"
elif [ -f "backend/.env" ]; then
    ENV_FILE="backend/.env"
else
    log_error "Không tìm thấy file cấu hình (.env.production hoặc backend/.env)"
    log_fix   "Tạo file cấu hình theo mẫu trong repo (cp .env.example .env.production)"
    exit 1
fi

log_success "Đọc cấu hình từ: $ENV_FILE"
# shellcheck source=/dev/null
set -a; source "$ENV_FILE"; set +a

echo ""
echo "  WAZUH_API_URL     : ${WAZUH_API_URL:-❌ Not set}"
echo "  WAZUH_API_USER    : ${WAZUH_API_USER:-❌ Not set}"
echo "  WAZUH_API_PASSWORD: ${WAZUH_API_PASSWORD:+****** (set)}"
echo "  WAZUH_VERIFY_SSL  : ${WAZUH_VERIFY_SSL:-true}"
echo "  ZABBIX_API_URL    : ${ZABBIX_API_URL:-❌ Not set}"
echo "  ZABBIX_API_USER   : ${ZABBIX_API_USER:-❌ Not set}"
echo "  ZABBIX_API_PASSWORD: ${ZABBIX_API_PASSWORD:+****** (set)}"
echo "  ZABBIX_API_TOKEN  : ${ZABBIX_API_TOKEN:+****** (set)}"
echo "  ZABBIX_ENABLED    : ${ZABBIX_ENABLED:-false}"
echo ""

#=============================================================================
# BƯỚC 2: KIỂM TRA WAZUH API
#=============================================================================
log_section "BƯỚC 2: Kiểm tra Wazuh API"

WAZUH_STATUS="UNKNOWN"
WAZUH_ERROR=""
WAZUH_FIX=""

if [ -z "${WAZUH_API_URL:-}" ]; then
    log_error "WAZUH_API_URL không được cấu hình"
    WAZUH_STATUS="NOT_CONFIGURED"
    WAZUH_ERROR="Biến WAZUH_API_URL chưa được đặt trong $ENV_FILE"
    WAZUH_FIX="Thêm dòng: WAZUH_API_URL=https://<IP-Wazuh-Manager>:55000"
else
    log_info "Testing Wazuh API: $WAZUH_API_URL"

    # Tách host và port từ URL
    WAZUH_HOST=$(echo "$WAZUH_API_URL" | sed -e 's|^[^/]*//||' -e 's|[:/].*||')
    WAZUH_PORT=$(echo "$WAZUH_API_URL" | grep -oP ':\K[0-9]+' || echo "55000")
    log_info "Host: $WAZUH_HOST   Port: $WAZUH_PORT"

    # ── Test W1: DNS resolution ─────────────────────────────────────────────
    log_info "W1: DNS resolution..."
    if getent hosts "$WAZUH_HOST" &>/dev/null; then
        W1_IP=$(getent hosts "$WAZUH_HOST" | awk '{print $1}')
        log_success "DNS OK → $W1_IP"
    else
        log_error "Không phân giải được hostname: $WAZUH_HOST"
        log_fix    "→ Kiểm tra DNS / /etc/hosts"
        log_fix    "→ Hoặc dùng địa chỉ IP trực tiếp trong WAZUH_API_URL"
        WAZUH_STATUS="DNS_FAILED"
        WAZUH_ERROR="DNS lookup thất bại cho $WAZUH_HOST"
        WAZUH_FIX="Đặt WAZUH_API_URL=https://<IP>:$WAZUH_PORT  (dùng IP, không dùng hostname)"
    fi

    # ── Test W2: TCP port ───────────────────────────────────────────────────
    if [ "$WAZUH_STATUS" != "DNS_FAILED" ]; then
        log_info "W2: TCP port $WAZUH_PORT..."
        if timeout 5 bash -c "echo >/dev/tcp/$WAZUH_HOST/$WAZUH_PORT" 2>/dev/null; then
            log_success "Port $WAZUH_PORT mở"
        else
            log_error "Port $WAZUH_PORT ĐÓNG trên $WAZUH_HOST"
            log_fix "Kiểm tra Wazuh Manager đang chạy:"
            log_fix "  systemctl status wazuh-manager"
            log_fix "  systemctl start wazuh-manager"
            log_fix "Kiểm tra firewall (ufw/iptables):"
            log_fix "  ufw allow $WAZUH_PORT/tcp"
            log_fix "  iptables -I INPUT -p tcp --dport $WAZUH_PORT -j ACCEPT"
            WAZUH_STATUS="PORT_CLOSED"
            WAZUH_ERROR="TCP port $WAZUH_PORT không thể kết nối"
            WAZUH_FIX="Khởi động wazuh-manager và mở firewall port $WAZUH_PORT"
        fi
    fi

    # ── Test W3: HTTPS/TLS ──────────────────────────────────────────────────
    if [ "$WAZUH_STATUS" = "UNKNOWN" ]; then
        log_info "W3: HTTPS/TLS handshake..."

        W3_OPTS="-s"
        [ "${WAZUH_VERIFY_SSL:-true}" = "false" ] && W3_OPTS="$W3_OPTS -k"

        W3_VERBOSE=$(curl --max-time 10 --connect-timeout 6 \
            $W3_OPTS -v "$WAZUH_API_URL" 2>&1 || true)
        W3_EXIT=${PIPESTATUS[0]}
        W3_CODE=$(curl --max-time 10 --connect-timeout 6 \
            $W3_OPTS -o /dev/null -w "%{http_code}" "$WAZUH_API_URL" 2>/dev/null) || W3_CODE="000"

        # Lấy thông tin TLS từ verbose output
        TLS_SUBJECT=$(echo "$W3_VERBOSE" | grep -i "subject:" | head -1 || echo "")
        TLS_ISSUER=$(echo "$W3_VERBOSE"  | grep -i "issuer:"  | head -1 || echo "")
        TLS_EXPIRE=$(echo "$W3_VERBOSE"  | grep -i "expire"   | head -1 || echo "")

        if [ "$W3_CODE" = "000" ]; then
            CURL_ERR_LINE=$(echo "$W3_VERBOSE" | grep "curl: (" | head -1 || echo "")
            log_error "HTTPS kết nối thất bại (HTTP 000)"
            echo ""
            echo "  ┌── CHI TIẾT LỖI TLS / CURL ──────────────────────────────────────"
            echo "$W3_VERBOSE" | grep -E "^\* |^> |error|SSL|TLS|certificate|connect" \
                              | head -25 | sed 's/^/  │ /'
            echo "  └──────────────────────────────────────────────────────────────────"
            echo ""

            # Phân tích lỗi TLS cụ thể
            if echo "$W3_VERBOSE" | grep -qi "SSL certificate problem\|certificate verify failed"; then
                log_error "→ Lỗi: SSL certificate không được tin cậy (self-signed hoặc CA không được cài)"
                log_fix   "Giải pháp 1 – Tắt SSL verify (phát triển):"
                log_fix   "  Đặt WAZUH_VERIFY_SSL=false trong $ENV_FILE"
                log_fix   "Giải pháp 2 – Thêm CA cert (production):"
                log_fix   "  Sao chép CA cert từ Wazuh Manager vào hệ thống:"
                log_fix   "  scp wazuh-manager:/var/ossec/etc/sslmanager.cert /usr/local/share/ca-certificates/"
                log_fix   "  update-ca-certificates"
                WAZUH_ERROR="SSL certificate verification failed"
                WAZUH_FIX="WAZUH_VERIFY_SSL=false  hoặc thêm CA cert của Wazuh vào trust store"
            elif echo "$W3_VERBOSE" | grep -qi "SSL handshake\|SSL_CTX\|ssl3_get_record"; then
                log_error "→ Lỗi: TLS Handshake thất bại"
                log_fix   "Kiểm tra Wazuh SSL config: /var/ossec/etc/api.yaml"
                log_fix   "Thử: curl -k $WAZUH_API_URL (nếu thành công → self-signed cert)"
                WAZUH_ERROR="TLS handshake failed"
                WAZUH_FIX="Đặt WAZUH_VERIFY_SSL=false trong $ENV_FILE để bỏ qua SSL verify"
            elif echo "$W3_VERBOSE" | grep -qi "Connection refused\|Failed to connect"; then
                log_error "→ Lỗi: Connection refused – Wazuh API daemon không chạy"
                log_fix   "Khởi động wazuh-manager: systemctl start wazuh-manager"
                WAZUH_ERROR="Connection refused"
                WAZUH_FIX="systemctl start wazuh-manager"
            elif echo "$W3_VERBOSE" | grep -qi "Could not resolve host"; then
                log_error "→ Lỗi: Không phân giải được hostname"
                WAZUH_ERROR="DNS resolution failed"
                WAZUH_FIX="Dùng IP address trực tiếp trong WAZUH_API_URL"
            else
                log_error "→ Lỗi HTTPS không xác định"
                WAZUH_ERROR="HTTPS connection failed (curl exit: $W3_EXIT)"
                WAZUH_FIX="Chạy thủ công: curl -v $WAZUH_API_URL để xem lỗi chi tiết"
            fi
            WAZUH_STATUS="HTTPS_FAILED"

        else
            [ -n "$TLS_SUBJECT" ] && log_detail "TLS Cert Subject : $TLS_SUBJECT"
            [ -n "$TLS_ISSUER"  ] && log_detail "TLS Cert Issuer  : $TLS_ISSUER"
            [ -n "$TLS_EXPIRE"  ] && log_detail "TLS Cert Expire  : $TLS_EXPIRE"
            log_success "HTTPS kết nối OK (HTTP $W3_CODE)"
        fi
    fi

    # ── Test W4: Authentication ─────────────────────────────────────────────
    if [ "$WAZUH_STATUS" = "UNKNOWN" ]; then
        log_info "W4: Authentication (Basic Auth → JWT)..."

        if [ -z "${WAZUH_API_USER:-}" ] || [ -z "${WAZUH_API_PASSWORD:-}" ]; then
            log_error "WAZUH_API_USER hoặc WAZUH_API_PASSWORD chưa được đặt"
            log_fix   "Thêm vào $ENV_FILE:"
            log_fix   "  WAZUH_API_USER=wazuh"
            log_fix   "  WAZUH_API_PASSWORD=<password>"
            log_fix   "Xem password mặc định: cat /var/ossec/.docker.env (trên Wazuh server)"
            WAZUH_STATUS="NO_CREDENTIALS"
            WAZUH_ERROR="Thiếu WAZUH_API_USER / WAZUH_API_PASSWORD"
            WAZUH_FIX="Thêm credentials vào $ENV_FILE"
        else
            W4_OPTS="-s"
            [ "${WAZUH_VERIFY_SSL:-true}" = "false" ] && W4_OPTS="$W4_OPTS -k"

            AUTH_RESPONSE=$(curl --max-time 15 --connect-timeout 8 \
                $W4_OPTS \
                -u "${WAZUH_API_USER}:${WAZUH_API_PASSWORD}" \
                -X POST \
                "${WAZUH_API_URL}/security/user/authenticate" 2>&1) || AUTH_RESPONSE="CURL_FAILED"
            W4_EXIT=$?
            W4_CODE=$(curl --max-time 15 --connect-timeout 8 \
                $W4_OPTS \
                -o /dev/null -w "%{http_code}" \
                -u "${WAZUH_API_USER}:${WAZUH_API_PASSWORD}" \
                -X POST \
                "${WAZUH_API_URL}/security/user/authenticate" 2>/dev/null) || W4_CODE="000"

            log_detail "Auth HTTP code: $W4_CODE"

            if echo "$AUTH_RESPONSE" | grep -q '"token"' 2>/dev/null; then
                WAZUH_TOKEN=$(echo "$AUTH_RESPONSE" | grep -o '"token":"[^"]*"' | cut -d'"' -f4 | tr -d '\r\n' || echo "")
                log_success "Xác thực thành công! Token nhận được: ${WAZUH_TOKEN:0:30}..."
                WAZUH_STATUS="OK"

                # ── Test W5: Agents ─────────────────────────────────────────
                log_info "W5: Lấy danh sách agents..."
                AGENTS_RESP=$(curl --max-time 15 $W4_OPTS \
                    -H "Authorization: Bearer $WAZUH_TOKEN" \
                    "${WAZUH_API_URL}/agents?limit=5" 2>/dev/null) || AGENTS_RESP=""

                if echo "$AGENTS_RESP" | grep -q '"total_affected_items"'; then
                    AGENT_COUNT=$(echo "$AGENTS_RESP" | grep -o '"total_affected_items":[0-9]*' | cut -d':' -f2 || echo "?")
                    log_success "Agents: $AGENT_COUNT agent(s) tìm thấy"
                    if [ "${AGENT_COUNT:-0}" = "0" ]; then
                        log_warning "Wazuh chưa có agent nào kết nối"
                        log_fix     "Cài đặt Wazuh agent trên các máy muốn giám sát"
                    fi
                else
                    log_warning "Không lấy được danh sách agents"
                    log_warning "Response: ${AGENTS_RESP:0:300}"
                fi

                # ── Test W6: Alerts API ─────────────────────────────────────
                log_info "W6: Kiểm tra Wazuh Alerts API..."
                ALERTS_RESP=$(curl --max-time 15 $W4_OPTS \
                    -H "Authorization: Bearer $WAZUH_TOKEN" \
                    "${WAZUH_API_URL}/security/events?limit=3" 2>/dev/null) || ALERTS_RESP=""

                if echo "$ALERTS_RESP" | grep -q '"total_affected_items"'; then
                    log_success "Alerts API OK"
                else
                    log_warning "Alerts API không phản hồi hoặc không có events"
                fi

            else
                log_error "Xác thực thất bại (HTTP $W4_CODE)"
                echo ""
                echo "  ┌── CHI TIẾT PHẢN HỒI TỪ WAZUH ────────────────────────────────"
                echo "$AUTH_RESPONSE" | head -20 | sed 's/^/  │ /'
                echo "  └───────────────────────────────────────────────────────────────"
                echo ""

                # Phân tích lỗi cụ thể
                if [ "$W4_CODE" = "401" ]; then
                    log_error "→ HTTP 401: Sai username hoặc password"
                    log_fix   "Cách 1 – Kiểm tra credentials trong $ENV_FILE"
                    log_fix   "Cách 2 – Xem/Reset password Wazuh:"
                    log_fix   "  # Trên Wazuh Manager server:"
                    log_fix   "  cat /var/ossec/.docker.env | grep API_PASSWORD"
                    log_fix   "  # Hoặc reset bằng CLI:"
                    log_fix   "  /var/ossec/bin/wazuh-passwords-tool -u wazuh -p <new_password>"
                    WAZUH_STATUS="INVALID_CREDENTIALS"
                    WAZUH_ERROR="HTTP 401 – Username hoặc password sai"
                    WAZUH_FIX="Kiểm tra WAZUH_API_USER và WAZUH_API_PASSWORD trong $ENV_FILE"

                elif [ "$W4_CODE" = "403" ]; then
                    log_error "→ HTTP 403: Tài khoản không có quyền"
                    log_fix   "Trên Wazuh Manager, cấp quyền cho user:"
                    log_fix   "  curl -k -u wazuh-wui:<pass> -X PUT $WAZUH_API_URL/security/users/<id>/roles"
                    WAZUH_STATUS="FORBIDDEN"
                    WAZUH_ERROR="HTTP 403 – Tài khoản không có quyền API"
                    WAZUH_FIX="Cấp role 'administrator' cho user trong Wazuh"

                elif [ "$W4_CODE" = "000" ]; then
                    CURL_EXIT_DESC=$(explain_curl_exit "$W4_EXIT")
                    log_error "→ curl exit $W4_EXIT: $CURL_EXIT_DESC"
                    WAZUH_STATUS="CURL_ERROR"
                    WAZUH_ERROR="curl exit $W4_EXIT – $CURL_EXIT_DESC"
                    WAZUH_FIX="$CURL_EXIT_DESC. Chạy: curl -v -k $WAZUH_API_URL để debug"

                elif echo "$AUTH_RESPONSE" | grep -qi "Connection refused"; then
                    log_error "→ Connection refused – Wazuh API service không chạy"
                    log_fix   "systemctl start wazuh-manager"
                    WAZUH_STATUS="CONNECTION_REFUSED"
                    WAZUH_ERROR="Connection refused"
                    WAZUH_FIX="systemctl start wazuh-manager  &&  systemctl enable wazuh-manager"

                else
                    log_error "→ Lỗi không xác định (HTTP $W4_CODE)"
                    WAZUH_STATUS="AUTH_FAILED"
                    WAZUH_ERROR="Auth failed HTTP $W4_CODE: ${AUTH_RESPONSE:0:150}"
                    WAZUH_FIX="Xem log Wazuh: journalctl -u wazuh-manager --since '5 min ago'"
                fi
            fi
        fi
    fi
fi

#=============================================================================
# BƯỚC 3: KIỂM TRA ZABBIX API
#=============================================================================
log_section "BƯỚC 3: Kiểm tra Zabbix API"

ZABBIX_STATUS="UNKNOWN"
ZABBIX_ERROR=""
ZABBIX_FIX=""

if [ "${ZABBIX_ENABLED:-false}" != "true" ]; then
    log_warning "Zabbix DISABLED (ZABBIX_ENABLED != true)"
    ZABBIX_STATUS="DISABLED"

elif [ -z "${ZABBIX_API_URL:-}" ]; then
    log_error "ZABBIX_API_URL không được cấu hình"
    log_fix   "Thêm vào $ENV_FILE: ZABBIX_API_URL=http://<IP-Zabbix>/zabbix/api_jsonrpc.php"
    ZABBIX_STATUS="NOT_CONFIGURED"
    ZABBIX_ERROR="ZABBIX_API_URL chưa được đặt"
    ZABBIX_FIX="Đặt ZABBIX_API_URL=http://<IP>/zabbix/api_jsonrpc.php trong $ENV_FILE"

else
    log_info "Testing Zabbix API: $ZABBIX_API_URL"

    ZABBIX_HOST=$(echo "$ZABBIX_API_URL" | sed -e 's|^[^/]*//||' -e 's|[:/].*||')
    log_info "Host: $ZABBIX_HOST"

    # ── Test Z1: DNS ────────────────────────────────────────────────────────
    log_info "Z1: DNS resolution..."
    if getent hosts "$ZABBIX_HOST" &>/dev/null; then
        log_success "DNS OK → $(getent hosts "$ZABBIX_HOST" | awk '{print $1}')"
    else
        log_error "Không phân giải được hostname: $ZABBIX_HOST"
        log_fix   "Dùng IP trực tiếp trong ZABBIX_API_URL"
        ZABBIX_STATUS="DNS_FAILED"
        ZABBIX_ERROR="DNS lookup thất bại cho $ZABBIX_HOST"
        ZABBIX_FIX="Đặt ZABBIX_API_URL=http://<IP>/zabbix/api_jsonrpc.php"
    fi

    # ── Test Z2: apiinfo.version (không cần auth) ───────────────────────────
    if [ "$ZABBIX_STATUS" = "UNKNOWN" ]; then
        log_info "Z2: Kiểm tra Zabbix API endpoint (apiinfo.version)..."

        Z2_PAYLOAD='{"jsonrpc":"2.0","method":"apiinfo.version","params":[],"id":1}'

        Z2_VERBOSE=$(curl --max-time 15 --connect-timeout 8 \
            -s -v -X POST \
            -H "Content-Type: application/json-rpc" \
            -d "$Z2_PAYLOAD" \
            "$ZABBIX_API_URL" 2>&1)
        Z2_BODY=$(curl --max-time 15 --connect-timeout 8 \
            -s -X POST \
            -H "Content-Type: application/json-rpc" \
            -d "$Z2_PAYLOAD" \
            "$ZABBIX_API_URL" 2>/dev/null) || Z2_BODY=""
        Z2_EXIT=$?
        Z2_CODE=$(curl --max-time 15 --connect-timeout 8 \
            -s -X POST \
            -H "Content-Type: application/json-rpc" \
            -d "$Z2_PAYLOAD" \
            -o /dev/null -w "%{http_code}" \
            "$ZABBIX_API_URL" 2>/dev/null) || Z2_CODE="000"

        log_detail "HTTP code: $Z2_CODE"

        if [ "$Z2_CODE" = "000" ]; then
            CURL_EXIT_DESC=$(explain_curl_exit "$Z2_EXIT")
            log_error "Không thể kết nối tới Zabbix API (HTTP 000)"
            log_error "curl exit $Z2_EXIT: $CURL_EXIT_DESC"
            echo ""
            echo "  ┌── CHI TIẾT LỖI CURL ───────────────────────────────────────────"
            echo "$Z2_VERBOSE" | grep -E "^\* |error|curl:|Failed|refused|timeout|SSL|TLS" \
                              | head -20 | sed 's/^/  │ /'
            echo "  └───────────────────────────────────────────────────────────────"
            echo ""

            if echo "$Z2_VERBOSE" | grep -qi "Connection refused"; then
                log_fix "Zabbix web server không chạy"
                log_fix "  systemctl status apache2   (hoặc nginx)"
                log_fix "  systemctl status zabbix-server"
                log_fix "  systemctl start apache2 zabbix-server"
                ZABBIX_ERROR="Connection refused – Zabbix web/app không chạy"
                ZABBIX_FIX="systemctl start apache2 zabbix-server  (hoặc nginx)"

            elif echo "$Z2_VERBOSE" | grep -qi "Could not resolve host"; then
                log_fix "Hostname không phân giải được"
                log_fix "  Dùng IP trực tiếp: ZABBIX_API_URL=http://<IP>/zabbix/api_jsonrpc.php"
                ZABBIX_ERROR="DNS resolution failed"
                ZABBIX_FIX="Đặt IP trực tiếp vào ZABBIX_API_URL"

            elif echo "$Z2_VERBOSE" | grep -qi "SSL\|TLS\|certificate"; then
                log_fix "Lỗi SSL/TLS:"
                log_fix "  Thêm -k vào curl (hoặc dùng HTTP thay HTTPS nếu Zabbix không có SSL)"
                log_fix "  Kiểm tra URL scheme: http:// hay https://"
                ZABBIX_ERROR="SSL/TLS error"
                ZABBIX_FIX="Kiểm tra URL scheme (http vs https) và cấu hình SSL Zabbix"

            elif echo "$Z2_VERBOSE" | grep -qi "timed out\|timeout"; then
                log_fix "Kết nối timeout – kiểm tra firewall:"
                log_fix "  ufw allow 80/tcp  (hoặc port Zabbix)"
                ZABBIX_ERROR="Connection timed out"
                ZABBIX_FIX="Mở firewall port 80/443 cho Zabbix"

            else
                log_fix "Lỗi không xác định – curl exit $Z2_EXIT: $CURL_EXIT_DESC"
                ZABBIX_ERROR="curl exit $Z2_EXIT – $CURL_EXIT_DESC"
                ZABBIX_FIX="Chạy: curl -v -X POST -H 'Content-Type: application/json-rpc' -d '$Z2_PAYLOAD' $ZABBIX_API_URL"
            fi
            ZABBIX_STATUS="CONNECTION_FAILED"

        elif [ "$Z2_CODE" = "200" ]; then
            ZABBIX_VERSION=$(echo "$Z2_BODY" | grep -o '"result":"[^"]*"' | cut -d'"' -f4 || echo "unknown")
            log_success "Zabbix API endpoint OK (HTTP 200)"
            log_success "Zabbix API version: $ZABBIX_VERSION"

            # ── Test Z3: Authentication ─────────────────────────────────────
            log_info "Z3: Authentication Zabbix API..."

            # Zabbix 5.4+ dùng "username" thay "user"
            ZABBIX_USER_KEY="user"
            if [[ "${ZABBIX_VERSION:-0}" > "5.3" ]]; then
                ZABBIX_USER_KEY="username"
            fi

            # Ưu tiên API token (Zabbix 5.4+) nếu có
            if [ -n "${ZABBIX_API_TOKEN:-}" ]; then
                log_info "Dùng API Token để xác thực (Zabbix ≥ 5.4)..."
                Z3_TEST=$(curl --max-time 15 -s -X POST "$ZABBIX_API_URL" \
                    -H "Content-Type: application/json-rpc" \
                    -H "Authorization: Bearer ${ZABBIX_API_TOKEN}" \
                    -d "{\"jsonrpc\":\"2.0\",\"method\":\"host.get\",\"params\":{\"limit\":1},\"id\":1}" \
                    2>/dev/null) || Z3_TEST=""

                if echo "$Z3_TEST" | grep -q '"result"'; then
                    log_success "API Token hợp lệ!"
                    ZABBIX_TOKEN="${ZABBIX_API_TOKEN}"
                    ZABBIX_STATUS="OK"
                else
                    log_error "API Token không hợp lệ"
                    log_detail "Response: ${Z3_TEST:0:200}"
                    log_fix   "Tạo API Token mới trong Zabbix UI:"
                    log_fix   "  Administration → API tokens → Create API token"
                    log_fix   "  Sau đó đặt ZABBIX_API_TOKEN=<token> trong $ENV_FILE"
                    ZABBIX_STATUS="INVALID_TOKEN"
                    ZABBIX_ERROR="API Token không hợp lệ hoặc hết hạn"
                    ZABBIX_FIX="Tạo mới API token trong Zabbix UI → Administration → API tokens"
                fi

            elif [ -n "${ZABBIX_API_USER:-}" ] && [ -n "${ZABBIX_API_PASSWORD:-}" ]; then
                log_info "Dùng username/password (user.login)..."

                Z3_PAYLOAD=$(printf '{"jsonrpc":"2.0","method":"user.login","params":{"%s":"%s","password":"%s"},"id":1}' \
                    "$ZABBIX_USER_KEY" "${ZABBIX_API_USER}" "${ZABBIX_API_PASSWORD}")

                Z3_BODY=$(curl --max-time 15 --connect-timeout 8 \
                    -s -X POST "$ZABBIX_API_URL" \
                    -H "Content-Type: application/json-rpc" \
                    -d "$Z3_PAYLOAD" 2>/dev/null) || Z3_BODY=""
                Z3_CODE=$(curl --max-time 15 --connect-timeout 8 \
                    -s -X POST "$ZABBIX_API_URL" \
                    -H "Content-Type: application/json-rpc" \
                    -d "$Z3_PAYLOAD" \
                    -o /dev/null -w "%{http_code}" 2>/dev/null) || Z3_CODE="000"

                log_detail "Auth HTTP code: $Z3_CODE"

                if echo "$Z3_BODY" | grep -q '"result"'; then
                    ZABBIX_TOKEN=$(echo "$Z3_BODY" | grep -o '"result":"[^"]*"' | cut -d'"' -f4 || echo "")
                    log_success "Xác thực thành công! Session token: ${ZABBIX_TOKEN:0:20}..."
                    ZABBIX_STATUS="OK"

                else
                    log_error "Zabbix authentication thất bại (HTTP $Z3_CODE)"
                    echo ""
                    echo "  ┌── CHI TIẾT PHẢN HỒI TỪ ZABBIX ──────────────────────────────"
                    echo "$Z3_BODY" | sed 's/^/  │ /'
                    echo "  └───────────────────────────────────────────────────────────────"
                    echo ""

                    # Phân tích JSON error từ Zabbix
                    ZBXERR_CODE=$(echo "$Z3_BODY" | grep -o '"code":-\?[0-9]*' | head -1 | grep -o -- '-\?[0-9]*' || echo "")
                    ZBXERR_MSG=$(echo  "$Z3_BODY" | grep -o '"message":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "")
                    ZBXERR_DATA=$(echo "$Z3_BODY" | grep -o '"data":"[^"]*"'    | head -1 | cut -d'"' -f4 || echo "")

                    if [ -n "$ZBXERR_CODE" ]; then
                        log_error "Zabbix JSON-RPC Error Code: $ZBXERR_CODE"
                        [ -n "$ZBXERR_MSG"  ] && log_error "Message: $ZBXERR_MSG"
                        [ -n "$ZBXERR_DATA" ] && log_error "Data   : $ZBXERR_DATA"
                        echo ""
                    fi

                    if echo "$Z3_BODY" | grep -qi "incorrect.*password\|Login name or password is incorrect"; then
                        log_fix "→ Username hoặc password sai"
                        log_fix "  Kiểm tra ZABBIX_API_USER và ZABBIX_API_PASSWORD trong $ENV_FILE"
                        log_fix "  Thử đăng nhập thủ công vào Zabbix web UI: http://$ZABBIX_HOST/zabbix"
                        log_fix "  Mặc định: Admin / zabbix  (đổi ngay sau khi cài!)"
                        ZABBIX_STATUS="INVALID_CREDENTIALS"
                        ZABBIX_ERROR="HTTP $Z3_CODE – Sai username/password"
                        ZABBIX_FIX="Kiểm tra ZABBIX_API_USER='Admin' và ZABBIX_API_PASSWORD đúng trong $ENV_FILE"

                    elif echo "$Z3_BODY" | grep -qi "Account is blocked\|blocked"; then
                        log_fix "→ Tài khoản bị BLOCK do đăng nhập sai quá nhiều lần"
                        log_fix "  Đăng nhập Zabbix DB để unblock:"
                        log_fix "  mysql -u zabbix -p zabbix -e \"UPDATE users SET attempt_failed=0 WHERE alias='Admin';\""
                        log_fix "  Hoặc PostgreSQL:"
                        log_fix "  psql -U zabbix -d zabbix -c \"UPDATE users SET attempt_failed=0 WHERE username='Admin';\""
                        log_fix "  Sau đó chờ 30 giây và thử lại"
                        ZABBIX_STATUS="ACCOUNT_BLOCKED"
                        ZABBIX_ERROR="Tài khoản bị block"
                        ZABBIX_FIX="Reset attempt_failed trong DB: UPDATE users SET attempt_failed=0,attempt_clock=0 WHERE username='Admin';"

                    elif echo "$Z3_BODY" | grep -qi "No permissions\|Not authorized"; then
                        log_fix "→ User không có quyền sử dụng API"
                        log_fix "  Trong Zabbix UI: Administration → Users → <user> → API access = Enable"
                        ZABBIX_STATUS="NO_API_PERMISSION"
                        ZABBIX_ERROR="User không có quyền API"
                        ZABBIX_FIX="Bật API access cho user trong Zabbix UI"

                    elif echo "$Z3_BODY" | grep -qi "username.*required\|user.*required"; then
                        log_fix "→ Có thể Zabbix version >= 5.4, cần dùng 'username' thay 'user'"
                        log_fix "  Kiểm tra Zabbix version: $ZABBIX_VERSION"
                        log_fix "  Đặt ZABBIX_API_VERSION trong $ENV_FILE để script chọn đúng key"
                        ZABBIX_STATUS="API_VERSION_MISMATCH"
                        ZABBIX_ERROR="API schema mismatch (user vs username field)"
                        ZABBIX_FIX="Zabbix >= 5.4: dùng 'username' field; đặt ZABBIX_API_TOKEN thay vì password"

                    elif [ -n "$ZBXERR_CODE" ]; then
                        log_fix "→ Zabbix API error code $ZBXERR_CODE: $ZBXERR_MSG"
                        ZABBIX_STATUS="API_ERROR"
                        ZABBIX_ERROR="Zabbix API error $ZBXERR_CODE: $ZBXERR_MSG ($ZBXERR_DATA)"
                        ZABBIX_FIX="Xem Zabbix documentation về error code $ZBXERR_CODE"

                    else
                        log_fix "→ Lỗi không xác định – xem raw response ở trên"
                        ZABBIX_STATUS="AUTH_FAILED"
                        ZABBIX_ERROR="Auth failed HTTP $Z3_CODE: ${Z3_BODY:0:150}"
                        ZABBIX_FIX="Xem log Zabbix: tail -f /var/log/zabbix/zabbix_server.log"
                    fi
                fi
            else
                log_error "Không có credentials Zabbix (cần ZABBIX_API_USER+PASSWORD hoặc ZABBIX_API_TOKEN)"
                log_fix   "Thêm vào $ENV_FILE:"
                log_fix   "  ZABBIX_API_USER=Admin"
                log_fix   "  ZABBIX_API_PASSWORD=<password>"
                log_fix   "Hoặc tạo API Token (khuyến nghị Zabbix ≥ 5.4):"
                log_fix   "  ZABBIX_API_TOKEN=<token>"
                ZABBIX_STATUS="NO_CREDENTIALS"
                ZABBIX_ERROR="Thiếu credentials Zabbix"
                ZABBIX_FIX="Thêm ZABBIX_API_USER + ZABBIX_API_PASSWORD vào $ENV_FILE"
            fi

            # ── Test Z4: Hosts list ─────────────────────────────────────────
            if [ "$ZABBIX_STATUS" = "OK" ] && [ -n "${ZABBIX_TOKEN:-}" ]; then
                log_info "Z4: Lấy danh sách hosts..."
                HOSTS_PAYLOAD='{"jsonrpc":"2.0","method":"host.get","params":{"output":["hostid","host"],"limit":5},"id":2}'
                HOSTS_RESP=$(curl --max-time 15 -s -X POST "$ZABBIX_API_URL" \
                    -H "Content-Type: application/json-rpc" \
                    -H "Authorization: Bearer $ZABBIX_TOKEN" \
                    -d "$HOSTS_PAYLOAD" 2>/dev/null) || HOSTS_RESP=""

                if echo "$HOSTS_RESP" | grep -q '"result"'; then
                    HOST_COUNT=$(echo "$HOSTS_RESP" | grep -o '"hostid"' | wc -l | tr -d ' ')
                    log_success "Zabbix hosts: $HOST_COUNT host(s) tìm thấy"
                    if [ "${HOST_COUNT:-0}" = "0" ]; then
                        log_warning "Zabbix chưa có host nào được monitor"
                        log_fix     "Thêm host trong Zabbix UI: Configuration → Hosts → Create host"
                    fi
                else
                    log_warning "Không lấy được danh sách hosts"
                    log_warning "Response: ${HOSTS_RESP:0:300}"
                fi
            fi

        else
            # HTTP code không phải 200 và không phải 000
            log_error "Zabbix API trả về HTTP $Z2_CODE"
            echo ""
            echo "  ┌── CHI TIẾT PHẢN HỒI ────────────────────────────────────────────"
            echo "$Z2_VERBOSE" | grep -v "^*" | tail -15 | sed 's/^/  │ /'
            echo "  └─────────────────────────────────────────────────────────────────"
            echo ""

            case "$Z2_CODE" in
                301|302|307|308)
                    NEW_LOCATION=$(echo "$Z2_VERBOSE" | grep -i "^< location:" | head -1 | awk '{print $3}' | tr -d '\r')
                    log_error "→ HTTP $Z2_CODE Redirect – URL có thể sai"
                    log_fix   "Thử URL mới: $NEW_LOCATION"
                    log_fix   "Hoặc kiểm tra lại ZABBIX_API_URL trong $ENV_FILE"
                    ZABBIX_ERROR="HTTP $Z2_CODE Redirect tới $NEW_LOCATION"
                    ZABBIX_FIX="Cập nhật ZABBIX_API_URL=$NEW_LOCATION"
                    ;;
                404)
                    log_error "→ HTTP 404 – Đường dẫn API không đúng"
                    log_fix   "URL Zabbix API thường là: http://<IP>/zabbix/api_jsonrpc.php"
                    log_fix   "Kiểm tra web server config của Zabbix"
                    ZABBIX_ERROR="HTTP 404 – API path không tồn tại"
                    ZABBIX_FIX="ZABBIX_API_URL đúng phải là http://<IP>/zabbix/api_jsonrpc.php"
                    ;;
                403)
                    log_error "→ HTTP 403 – Web server từ chối request (IP ban / WAF)"
                    log_fix   "Kiểm tra Zabbix AllowedHosts trong zabbix_server.conf"
                    log_fix   "  AllowedHosts=127.0.0.1,<IP-Mini-SOC>"
                    ZABBIX_ERROR="HTTP 403 – Access denied"
                    ZABBIX_FIX="Thêm IP Mini-SOC vào AllowedHosts trong /etc/zabbix/zabbix_server.conf"
                    ;;
                500|502|503)
                    log_error "→ HTTP $Z2_CODE – Server error, Zabbix service có vấn đề"
                    log_fix   "  systemctl status zabbix-server"
                    log_fix   "  tail -100 /var/log/zabbix/zabbix_server.log"
                    ZABBIX_ERROR="HTTP $Z2_CODE – Server internal error"
                    ZABBIX_FIX="Kiểm tra logs: tail -f /var/log/zabbix/zabbix_server.log"
                    ;;
                *)
                    log_error "→ HTTP $Z2_CODE – Lỗi không xác định"
                    ZABBIX_ERROR="HTTP $Z2_CODE"
                    ZABBIX_FIX="Chạy: curl -v -X POST -H 'Content-Type: application/json-rpc' -d '$Z2_PAYLOAD' $ZABBIX_API_URL"
                    ;;
            esac
            ZABBIX_STATUS="HTTP_ERROR"
        fi
    fi
fi

#=============================================================================
# BƯỚC 4: KIỂM TRA MINI-SOC BACKEND
#=============================================================================
log_section "BƯỚC 4: Kiểm tra Mini-SOC Backend"

BACKEND_STATUS="UNKNOWN"
BACKEND_CONTAINER=$(docker ps --filter "name=backend" --format "{{.Names}}" 2>/dev/null | head -1 || echo "")

if [ -n "$BACKEND_CONTAINER" ]; then
    log_success "Backend container đang chạy: $BACKEND_CONTAINER"
    BACKEND_STATUS="RUNNING"

    # Lấy 100 dòng log mới nhất
    BACKEND_LOGS=$(docker logs "$BACKEND_CONTAINER" --tail 100 2>&1 || echo "")

    for svc in wazuh zabbix; do
        ERRS=$(echo "$BACKEND_LOGS" | grep -i "$svc" | grep -iE "error|failed|refused|timeout|exception" | tail -5)
        if [ -n "$ERRS" ]; then
            log_warning "Lỗi $svc trong backend logs:"
            echo "$ERRS" | sed 's/^/    /'
        else
            log_info "Không phát hiện lỗi $svc trong logs"
        fi
    done

    # Collector stats
    if echo "$BACKEND_LOGS" | grep -q "collector_stats"; then
        LAST_STAT=$(echo "$BACKEND_LOGS" | grep "collector_stats" | tail -1)
        log_success "Collector stats: $LAST_STAT"
    else
        log_warning "Chưa có collector_stats – collector có thể chưa xử lý events nào"
    fi
else
    log_error "Backend container KHÔNG chạy"
    log_fix   "docker compose up -d backend   (hoặc docker-compose up -d backend)"
    BACKEND_STATUS="NOT_RUNNING"
fi

#=============================================================================
# BƯỚC 5: KIỂM TRA DATABASE
#=============================================================================
log_section "BƯỚC 5: Kiểm tra Database"

WAZUH_EVENTS="0"
AGENTS="0"
DB_CONTAINER=$(docker ps --filter "name=db" --format "{{.Names}}" 2>/dev/null | head -1 || echo "")

if [ -n "$DB_CONTAINER" ]; then
    log_success "DB container: $DB_CONTAINER"
    DB_NAME="${POSTGRES_DB:-mini_soc_prod}"

    WAZUH_EVENTS=$(docker exec "$DB_CONTAINER" psql -U postgres -d "$DB_NAME" \
        -tAc "SELECT COUNT(*) FROM wazuh_events;" 2>/dev/null | tr -d '\r\n' || echo "0")
    AGENTS=$(docker exec "$DB_CONTAINER" psql -U postgres -d "$DB_NAME" \
        -tAc "SELECT COUNT(*) FROM endpoint_inventory;" 2>/dev/null | tr -d '\r\n' || echo "0")

    log_info "Wazuh events trong DB  : $WAZUH_EVENTS"
    log_info "Agents trong DB        : $AGENTS"

    if [ "${WAZUH_EVENTS:-0}" -gt 0 ] 2>/dev/null; then
        log_success "DB có $WAZUH_EVENTS wazuh events"
        docker exec "$DB_CONTAINER" psql -U postgres -d "$DB_NAME" \
            -c "SELECT event_timestamp, severity, agent_name FROM wazuh_events ORDER BY event_timestamp DESC LIMIT 3;" \
            2>/dev/null || true
    else
        log_warning "DB không có wazuh events – collector chưa thu thập được dữ liệu"
    fi
else
    log_error "DB container không chạy"
    log_fix   "docker compose up -d db"
fi

#=============================================================================
# BƯỚC 6: TÓM TẮT VÀ HƯỚNG DẪN KHẮC PHỤC
#=============================================================================
log_section "BÁO CÁO CHẨN ĐOÁN & HƯỚNG DẪN KHẮC PHỤC"

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                   DIAGNOSTIC SUMMARY                            ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# ── Wazuh ────────────────────────────────────────────────────────────────────
printf "%-20s : %s\n" "WAZUH API" "$WAZUH_STATUS"
case "$WAZUH_STATUS" in
    OK)
        echo -e "  ${GREEN}✓ Wazuh API hoạt động bình thường${NC}" ;;
    DISABLED)
        echo -e "  ${YELLOW}⚠ Wazuh API không được sử dụng${NC}" ;;
    NOT_CONFIGURED)
        echo -e "  ${RED}✗ Chưa cấu hình${NC}"
        echo    "  Lỗi : $WAZUH_ERROR"
        echo -e "  ${MAGENTA}Fix : $WAZUH_FIX${NC}" ;;
    PORT_CLOSED|DNS_FAILED|HTTPS_FAILED|CONNECTION_REFUSED|CURL_ERROR)
        echo -e "  ${RED}✗ Không kết nối được${NC}"
        echo    "  Lỗi : $WAZUH_ERROR"
        echo -e "  ${MAGENTA}Fix : $WAZUH_FIX${NC}" ;;
    INVALID_CREDENTIALS)
        echo -e "  ${RED}✗ Sai credentials${NC}"
        echo    "  Lỗi : $WAZUH_ERROR"
        echo -e "  ${MAGENTA}Fix : $WAZUH_FIX${NC}" ;;
    FORBIDDEN)
        echo -e "  ${RED}✗ Không có quyền${NC}"
        echo    "  Lỗi : $WAZUH_ERROR"
        echo -e "  ${MAGENTA}Fix : $WAZUH_FIX${NC}" ;;
    NO_CREDENTIALS)
        echo -e "  ${RED}✗ Thiếu credentials${NC}"
        echo    "  Lỗi : $WAZUH_ERROR"
        echo -e "  ${MAGENTA}Fix : $WAZUH_FIX${NC}" ;;
    *)
        echo -e "  ${RED}✗ Lỗi: $WAZUH_STATUS${NC}"
        echo    "  Lỗi : $WAZUH_ERROR"
        [ -n "$WAZUH_FIX" ] && echo -e "  ${MAGENTA}Fix : $WAZUH_FIX${NC}" ;;
esac
echo ""

# ── Zabbix ───────────────────────────────────────────────────────────────────
printf "%-20s : %s\n" "ZABBIX API" "$ZABBIX_STATUS"
case "$ZABBIX_STATUS" in
    OK)
        echo -e "  ${GREEN}✓ Zabbix API hoạt động bình thường${NC}" ;;
    DISABLED)
        echo -e "  ${YELLOW}⚠ Zabbix bị tắt (ZABBIX_ENABLED=false)${NC}"
        echo    "  Fix : Đặt ZABBIX_ENABLED=true trong $ENV_FILE nếu muốn dùng Zabbix" ;;
    NOT_CONFIGURED)
        echo -e "  ${RED}✗ Chưa cấu hình${NC}"
        echo    "  Lỗi : $ZABBIX_ERROR"
        echo -e "  ${MAGENTA}Fix : $ZABBIX_FIX${NC}" ;;
    CONNECTION_FAILED|DNS_FAILED|HTTP_ERROR)
        echo -e "  ${RED}✗ Không kết nối được${NC}"
        echo    "  Lỗi : $ZABBIX_ERROR"
        echo -e "  ${MAGENTA}Fix : $ZABBIX_FIX${NC}" ;;
    INVALID_CREDENTIALS|ACCOUNT_BLOCKED|NO_API_PERMISSION|INVALID_TOKEN|API_VERSION_MISMATCH)
        echo -e "  ${RED}✗ Lỗi xác thực${NC}"
        echo    "  Lỗi : $ZABBIX_ERROR"
        echo -e "  ${MAGENTA}Fix : $ZABBIX_FIX${NC}" ;;
    NO_CREDENTIALS)
        echo -e "  ${RED}✗ Thiếu credentials${NC}"
        echo    "  Lỗi : $ZABBIX_ERROR"
        echo -e "  ${MAGENTA}Fix : $ZABBIX_FIX${NC}" ;;
    *)
        echo -e "  ${RED}✗ Lỗi: $ZABBIX_STATUS${NC}"
        echo    "  Lỗi : $ZABBIX_ERROR"
        [ -n "$ZABBIX_FIX" ] && echo -e "  ${MAGENTA}Fix : $ZABBIX_FIX${NC}" ;;
esac
echo ""

# ── Backend ───────────────────────────────────────────────────────────────────
printf "%-20s : %s\n" "BACKEND" "$BACKEND_STATUS"
if [ "$BACKEND_STATUS" = "RUNNING" ]; then
    echo -e "  ${GREEN}✓ Backend container đang chạy${NC}"
else
    echo -e "  ${RED}✗ Backend không chạy${NC}"
    echo -e "  ${MAGENTA}Fix : docker compose up -d backend${NC}"
fi
echo ""

# ── Database ──────────────────────────────────────────────────────────────────
printf "%-20s : %s events / %s agents\n" "DATABASE" "${WAZUH_EVENTS:-0}" "${AGENTS:-0}"
if [ "${WAZUH_EVENTS:-0}" -gt 0 ] 2>/dev/null; then
    echo -e "  ${GREEN}✓ Có $WAZUH_EVENTS wazuh events trong DB${NC}"
else
    echo -e "  ${YELLOW}⚠ Chưa có wazuh events trong DB${NC}"
fi
echo ""

# ── Kết luận ──────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                      KẾT LUẬN                                   ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

if [ "$WAZUH_STATUS" = "OK" ] && [ "$ZABBIX_STATUS" = "OK" ] && [ "${WAZUH_EVENTS:-0}" -gt 0 ] 2>/dev/null; then
    echo -e "${GREEN}✓ HỆ THỐNG HOẠT ĐỘNG BÌNH THƯỜNG${NC}"
    echo "  Cả Wazuh và Zabbix API đều kết nối tốt, DB có dữ liệu."

elif [ "$WAZUH_STATUS" != "OK" ]; then
    echo -e "${RED}✗ VẤN ĐỀ CHÍNH: WAZUH API – $WAZUH_STATUS${NC}"
    echo ""
    echo "  Lỗi chi tiết: $WAZUH_ERROR"
    echo ""
    echo "  ── HƯỚNG DẪN KHẮC PHỤC WAZUH ────────────────────────────────────"
    case "$WAZUH_STATUS" in
        PORT_CLOSED)
            echo "  1. SSH vào Wazuh Manager và kiểm tra:"
            echo "       systemctl status wazuh-manager"
            echo "       ss -tlnp | grep 55000"
            echo "  2. Khởi động nếu cần:"
            echo "       systemctl enable --now wazuh-manager"
            echo "  3. Mở firewall:"
            echo "       ufw allow 55000/tcp"
            echo "       firewall-cmd --permanent --add-port=55000/tcp --zone=public && firewall-cmd --reload"
            ;;
        HTTPS_FAILED)
            echo "  1. Test bỏ qua SSL:"
            echo "       curl -k $WAZUH_API_URL"
            echo "  2. Nếu thành công với -k → đặt WAZUH_VERIFY_SSL=false trong $ENV_FILE"
            echo "  3. Để dùng SSL đúng, thêm CA cert của Wazuh:"
            echo "       scp wazuh-manager:/var/ossec/etc/sslmanager.cert /usr/local/share/ca-certificates/wazuh-ca.crt"
            echo "       update-ca-certificates"
            ;;
        INVALID_CREDENTIALS)
            echo "  1. Lấy password hiện tại của Wazuh:"
            echo "       cat /var/ossec/.docker.env | grep -i password   (nếu dùng Docker)"
            echo "       cat /var/ossec/api/configuration/security/users.yaml"
            echo "  2. Reset password:"
            echo "       /var/ossec/bin/wazuh-passwords-tool -u wazuh -p <new_password>"
            echo "  3. Cập nhật $ENV_FILE:"
            echo "       WAZUH_API_USER=wazuh"
            echo "       WAZUH_API_PASSWORD=<new_password>"
            ;;
        NOT_CONFIGURED)
            echo "  1. Tìm IP Wazuh Manager: ping wazuh-manager  hoặc  ip addr"
            echo "  2. Thêm vào $ENV_FILE:"
            echo "       WAZUH_API_URL=https://<IP>:55000"
            echo "       WAZUH_API_USER=wazuh"
            echo "       WAZUH_API_PASSWORD=<password>"
            echo "       WAZUH_VERIFY_SSL=false"
            ;;
        *)
            echo "  $WAZUH_FIX"
            ;;
    esac
    echo "  ──────────────────────────────────────────────────────────────────"

elif [ "$ZABBIX_STATUS" != "OK" ] && [ "$ZABBIX_STATUS" != "DISABLED" ] && [ "$ZABBIX_STATUS" != "NOT_CONFIGURED" ]; then
    echo -e "${RED}✗ VẤN ĐỀ CHÍNH: ZABBIX API – $ZABBIX_STATUS${NC}"
    echo ""
    echo "  Lỗi chi tiết: $ZABBIX_ERROR"
    echo ""
    echo "  ── HƯỚNG DẪN KHẮC PHỤC ZABBIX ────────────────────────────────────"
    case "$ZABBIX_STATUS" in
        CONNECTION_FAILED)
            echo "  1. Kiểm tra Zabbix server và web:"
            echo "       systemctl status zabbix-server apache2 php-fpm"
            echo "  2. Khởi động các service:"
            echo "       systemctl enable --now zabbix-server apache2"
            echo "  3. Test trực tiếp:"
            echo "       curl -X POST -H 'Content-Type: application/json-rpc' \\"
            echo "            -d '{\"jsonrpc\":\"2.0\",\"method\":\"apiinfo.version\",\"params\":[],\"id\":1}' \\"
            echo "            $ZABBIX_API_URL"
            ;;
        INVALID_CREDENTIALS)
            echo "  1. Thử đăng nhập vào Zabbix UI: http://$ZABBIX_HOST/zabbix"
            echo "     Default: Admin / zabbix"
            echo "  2. Cập nhật $ENV_FILE:"
            echo "       ZABBIX_API_USER=Admin"
            echo "       ZABBIX_API_PASSWORD=<correct_password>"
            ;;
        ACCOUNT_BLOCKED)
            echo "  1. Unblock trong Zabbix DB (MySQL):"
            echo "       mysql -u zabbix -p zabbix -e \"UPDATE users SET attempt_failed=0,attempt_clock=0 WHERE username='Admin';\""
            echo "  2. Unblock trong Zabbix DB (PostgreSQL):"
            echo "       psql -U zabbix -d zabbix -c \"UPDATE users SET attempt_failed=0,attempt_clock=0 WHERE username='Admin';\""
            echo "  3. Restart zabbix-server và đợi 30 giây"
            ;;
        HTTP_ERROR)
            echo "  $ZABBIX_FIX"
            ;;
        API_VERSION_MISMATCH)
            echo "  Zabbix >= 5.4 dùng 'username' thay 'user' trong user.login"
            echo "  Khuyến nghị: Dùng API Token thay username/password"
            echo "  1. Tạo API Token: Zabbix UI → Administration → API tokens"
            echo "  2. Thêm vào $ENV_FILE: ZABBIX_API_TOKEN=<token>"
            ;;
        *)
            echo "  $ZABBIX_FIX"
            ;;
    esac
    echo "  ──────────────────────────────────────────────────────────────────"

elif [ "${WAZUH_EVENTS:-0}" -eq 0 ] 2>/dev/null; then
    echo -e "${YELLOW}⚠ API KẾT NỐI OK NHƯNG CHƯA CÓ DỮ LIỆU${NC}"
    echo ""
    echo "  Wazuh API OK nhưng DB không có events."
    echo "  Có thể do:"
    echo "    1. Wazuh chưa có agent nào kết nối → /var/ossec/bin/agent_control -l"
    echo "    2. Alerts file trống → tail -f /var/ossec/logs/alerts/alerts.json"
    echo "    3. Volume mount sai trong docker-compose.yml"
    echo "    4. Collector chưa chạy → kiểm tra backend logs"
    echo ""
    echo "  Nhanh nhất: inject test data để kiểm tra UI:"
    echo "    bash inject_test_data.sh"
fi

echo ""

# ── Lưu báo cáo ──────────────────────────────────────────────────────────────
REPORT_FILE="api_diagnostic_$(date +%Y%m%d_%H%M%S).txt"
{
    echo "Mini-SOC API Diagnostic Report"
    echo "Generated   : $(date)"
    echo "Config file : $ENV_FILE"
    echo ""
    echo "WAZUH_STATUS  : $WAZUH_STATUS"
    echo "WAZUH_ERROR   : ${WAZUH_ERROR:-none}"
    echo "WAZUH_FIX     : ${WAZUH_FIX:-none}"
    echo ""
    echo "ZABBIX_STATUS : $ZABBIX_STATUS"
    echo "ZABBIX_ERROR  : ${ZABBIX_ERROR:-none}"
    echo "ZABBIX_FIX    : ${ZABBIX_FIX:-none}"
    echo ""
    echo "BACKEND       : $BACKEND_STATUS"
    echo "WAZUH_EVENTS  : $WAZUH_EVENTS"
    echo "AGENTS        : $AGENTS"
} > "$REPORT_FILE"

log_success "Báo cáo đã lưu: $REPORT_FILE"
echo ""
echo "Để xem log chi tiết:"
echo "  docker logs <container-name> --tail 100"
echo "  journalctl -u wazuh-manager --since '30 min ago'"
echo ""
