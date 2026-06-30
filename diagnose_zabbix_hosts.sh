#!/bin/bash
# ==========================================================================
#  diagnose_zabbix_hosts.sh
#  Chẩn đoán tại sao host Zabbix không lấy được trạng thái đúng.
#  Chỉ cần: curl + jq (không cần Python, không cần cài thêm gì)
#
#  Cách dùng:
#    chmod +x diagnose_zabbix_hosts.sh
#    ./diagnose_zabbix_hosts.sh
#
#  Hoặc truyền biến môi trường:
#    ZABBIX_URL=http://192.168.1.10/api_jsonrpc.php \
#    ZABBIX_USER=Admin \
#    ZABBIX_PASS=zabbix \
#    ./diagnose_zabbix_hosts.sh
#
#  Lọc theo host cụ thể:
#    ./diagnose_zabbix_hosts.sh --host-id 10084
#    ./diagnose_zabbix_hosts.sh --host-name "web-server"
#    ./diagnose_zabbix_hosts.sh --protocol "HTTP Agent"
# ==========================================================================

set -euo pipefail

# ─── Màu sắc ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

log_ok()      { echo -e "${GREEN}[✓]${NC}  $*"; }
log_warn()    { echo -e "${YELLOW}[⚠]${NC}  $*"; }
log_error()   { echo -e "${RED}[✗]${NC}  $*"; }
log_info()    { echo -e "${BLUE}[i]${NC}  $*"; }
log_section() {
    echo -e "\n${BOLD}${CYAN}══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  $*${NC}"
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════════════════════${NC}"
}
log_sub()     { echo -e "    ${CYAN}▸${NC} $*"; }

# ─── Cấu hình (đọc từ .env nếu có) ───────────────────────────────────────
ENV_FILE="${ENV_FILE:-.env}"
if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

ZABBIX_URL="${ZABBIX_URL:-${ZABBIX_API_URL:-http://localhost/api_jsonrpc.php}}"
ZABBIX_USER="${ZABBIX_USER:-${ZABBIX_API_USER:-Admin}}"
ZABBIX_PASS="${ZABBIX_PASS:-${ZABBIX_API_PASSWORD:-zabbix}}"

# ─── Tham số dòng lệnh ────────────────────────────────────────────────────
FILTER_HOST_ID=""
FILTER_HOST_NAME=""
FILTER_PROTOCOL=""
VERBOSE=false
SUMMARY_ONLY=false
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host-id)    FILTER_HOST_ID="$2";   shift 2 ;;
        --host-name)  FILTER_HOST_NAME="$2"; shift 2 ;;
        --protocol)   FILTER_PROTOCOL="$2";  shift 2 ;;
        --verbose|-v) VERBOSE=true;          shift   ;;
        --summary)    SUMMARY_ONLY=true;     shift   ;;
        --output|-o)  OUTPUT_FILE="$2";      shift 2 ;;
        --url)        ZABBIX_URL="$2";       shift 2 ;;
        --user)       ZABBIX_USER="$2";      shift 2 ;;
        --pass)       ZABBIX_PASS="$2";      shift 2 ;;
        --help|-h)
            echo "Cách dùng: $0 [options]"
            echo "  --host-id   <id>        Lọc theo hostid"
            echo "  --host-name <tên>       Lọc theo tên host (substring)"
            echo "  --protocol  <giao thức> Lọc: 'HTTP Agent', 'Zabbix Agent', 'SNMP', 'IPMI'"
            echo "  --verbose,-v            Hiện trace chi tiết"
            echo "  --summary               Chỉ hiện summary cuối"
            echo "  --output,-o <file>      Ghi kết quả JSON ra file"
            echo "  --url <url>             Zabbix API URL"
            echo "  --user <user>           Zabbix username"
            echo "  --pass <pass>           Zabbix password"
            exit 0 ;;
        *) echo "Tham số không hợp lệ: $1"; exit 1 ;;
    esac
done

# ─── Kiểm tra dependencies ────────────────────────────────────────────────
log_section "KIỂM TRA DEPENDENCIES"

for cmd in curl jq; do
    if command -v "$cmd" &>/dev/null; then
        log_ok "$cmd đã cài đặt ($(command -v $cmd))"
    else
        log_error "$cmd chưa được cài. Chạy: apt-get install $cmd"
        exit 1
    fi
done

# ─── Helper: gọi Zabbix API ───────────────────────────────────────────────
zabbix_call() {
    local method="$1"
    local params="$2"
    local token="${3:-}"

    local payload
    if [[ -n "$token" ]]; then
        payload=$(jq -cn \
            --arg method "$method" \
            --argjson params "$params" \
            '{"jsonrpc":"2.0","method":$method,"params":$params,"id":1}')
    else
        payload=$(jq -cn \
            --arg method "$method" \
            --argjson params "$params" \
            '{"jsonrpc":"2.0","method":$method,"params":$params,"id":1}')
    fi

    local response
    if [[ -n "$token" ]]; then
        response=$(curl -s --max-time 30 -X POST "$ZABBIX_URL" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $token" \
            -d "$payload" 2>/dev/null)
    else
        response=$(curl -s --max-time 30 -X POST "$ZABBIX_URL" \
            -H "Content-Type: application/json" \
            -d "$payload" 2>/dev/null)
    fi

    echo "$response"
}

# ─── BƯỚC 1: Kết nối API ─────────────────────────────────────────────────
log_section "BƯỚC 1: KIỂM TRA KẾT NỐI ZABBIX API"
log_info "URL: $ZABBIX_URL"
log_info "User: $ZABBIX_USER"

VERSION_RESP=$(curl -s --max-time 10 -X POST "$ZABBIX_URL" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"apiinfo.version","params":[],"id":0}' 2>/dev/null || echo "")

if [[ -z "$VERSION_RESP" ]]; then
    log_error "Không thể kết nối đến $ZABBIX_URL (timeout hoặc từ chối kết nối)"
    exit 1
fi

ZABBIX_VERSION=$(echo "$VERSION_RESP" | jq -r '.result // empty' 2>/dev/null || echo "")
if [[ -z "$ZABBIX_VERSION" ]]; then
    log_error "API trả về lỗi: $(echo "$VERSION_RESP" | jq -r '.error.data // .error // "unknown"' 2>/dev/null)"
    exit 1
fi
log_ok "Kết nối thành công — Zabbix phiên bản: ${BOLD}$ZABBIX_VERSION${NC}"

# ─── BƯỚC 2: Xác thực ────────────────────────────────────────────────────
log_section "BƯỚC 2: XÁC THỰC"

AUTH_RESP=$(zabbix_call "user.login" \
    "{\"username\":\"$ZABBIX_USER\",\"password\":\"$ZABBIX_PASS\"}")

TOKEN=$(echo "$AUTH_RESP" | jq -r '.result // empty' 2>/dev/null || echo "")
if [[ -z "$TOKEN" ]]; then
    AUTH_ERR=$(echo "$AUTH_RESP" | jq -r '.error.data // .error.message // "Sai thông tin đăng nhập"' 2>/dev/null)
    log_error "Xác thực thất bại: $AUTH_ERR"
    exit 1
fi
log_ok "Token nhận được: ${TOKEN:0:12}..."

# ─── BƯỚC 3: Lấy danh sách hosts ─────────────────────────────────────────
log_section "BƯỚC 3: LẤY DANH SÁCH HOST"

HOST_PARAMS=$(jq -cn '{
    "output": [
        "hostid","host","name","status",
        "available","snmp_available","ipmi_available","jmx_available",
        "maintenance_status","error","description"
    ],
    "selectInterfaces": "extend",
    "selectGroups": "extend",
    "selectParentTemplates": ["name"],
    "filter": {"status": "0"}
}')

HOST_RESP=$(zabbix_call "host.get" "$HOST_PARAMS" "$TOKEN")
HOST_ERR=$(echo "$HOST_RESP" | jq -r '.error.data // empty' 2>/dev/null || echo "")

if [[ -n "$HOST_ERR" ]]; then
    log_error "host.get thất bại: $HOST_ERR"
    exit 1
fi

TOTAL_HOSTS=$(echo "$HOST_RESP" | jq '.result | length')
log_ok "Nhận được ${BOLD}$TOTAL_HOSTS${NC} host từ Zabbix"

# ─── BƯỚC 4: Lấy items (để kiểm tra HTTP Agent availability) ─────────────
log_section "BƯỚC 4: LẤY ITEMS (PHỤC VỤ KIỂM TRA HTTP AGENT)"

HOST_IDS=$(echo "$HOST_RESP" | jq -r '[.result[].hostid]')
ITEM_PARAMS=$(jq -cn \
    --argjson hostids "$HOST_IDS" \
    '{
        "output": ["itemid","hostid","name","key_","status","state","type","error","lastvalue","lastclock"],
        "hostids": $hostids,
        "filter": {"status": "0"},
        "limit": 50000
    }')

ITEM_RESP=$(zabbix_call "item.get" "$ITEM_PARAMS" "$TOKEN")
TOTAL_ITEMS=$(echo "$ITEM_RESP" | jq '.result | length // 0' 2>/dev/null || echo "0")
log_ok "Nhận được ${BOLD}$TOTAL_ITEMS${NC} items"

# ─── BƯỚC 5: Phân tích từng host ─────────────────────────────────────────
log_section "BƯỚC 5: PHÂN TÍCH TỪNG HOST"

# Bộ đếm tổng hợp
CNT_AVAILABLE=0
CNT_UNAVAILABLE=0
CNT_UNKNOWN=0
CNT_ZABBIX_AGENT=0
CNT_HTTP_AGENT=0
CNT_SNMP=0
CNT_IPMI=0
CNT_JMX=0
CNT_ACTIVE=0
CNT_UNRESOLVED=0
CNT_MAINT=0
CNT_ERROR=0

# Mảng lưu JSON kết quả
declare -a REPORT_ENTRIES=()

HOSTS_JSON=$(echo "$HOST_RESP" | jq -c '.result[]')

while IFS= read -r host; do
    HOST_ID=$(echo "$host" | jq -r '.hostid')
    HOST_NAME=$(echo "$host" | jq -r '.name // .host')
    HOST_TECHNICAL=$(echo "$host" | jq -r '.host')
    MAINT=$(echo "$host" | jq -r '.maintenance_status // "0"')
    ZABBIX_ERR=$(echo "$host" | jq -r '.error // ""')

    # ── Lọc theo tham số đầu vào ──────────────────────────────────────────
    if [[ -n "$FILTER_HOST_ID" && "$HOST_ID" != "$FILTER_HOST_ID" ]]; then continue; fi
    if [[ -n "$FILTER_HOST_NAME" ]]; then
        if ! echo "$HOST_NAME $HOST_TECHNICAL" | grep -qi "$FILTER_HOST_NAME"; then continue; fi
    fi

    # ── Đọc top-level availability ────────────────────────────────────────
    AVAIL_AGENT=$(echo "$host" | jq -r '.available // "0"')
    AVAIL_SNMP=$(echo "$host" | jq -r '.snmp_available // "0"')
    AVAIL_IPMI=$(echo "$host" | jq -r '.ipmi_available // "0"')
    AVAIL_JMX=$(echo "$host" | jq -r '.jmx_available // "0"')

    # ── Interfaces ────────────────────────────────────────────────────────
    IFACE_COUNT=$(echo "$host" | jq '.interfaces | length // 0')
    IFACE_TYPES=$(echo "$host" | jq -r '[.interfaces[]?.type // "?"] | join(",")')
    PRIMARY_IP=$(echo "$host" | jq -r '
        (.interfaces // []) |
        (map(select(.main == "1" or .main == 1)) | first // .[0]) |
        .ip // .dns // ""
    ')

    # ── Phát hiện giao thức (4 bước) ─────────────────────────────────────
    AGENT_TYPES_ARR=()
    TRACE=""

    # Step 1: top-level
    [[ "$AVAIL_AGENT" != "0" ]] && AGENT_TYPES_ARR+=("Zabbix Agent")
    [[ "$AVAIL_SNMP"  != "0" ]] && AGENT_TYPES_ARR+=("SNMP")
    [[ "$AVAIL_IPMI"  != "0" ]] && AGENT_TYPES_ARR+=("IPMI")
    [[ "$AVAIL_JMX"   != "0" ]] && AGENT_TYPES_ARR+=("JMX")
    TRACE+="[Step1] avail=${AVAIL_AGENT} snmp=${AVAIL_SNMP} ipmi=${AVAIL_IPMI} jmx=${AVAIL_JMX}"$'\n'

    # Step 2: interface types
    if [[ $IFACE_COUNT -gt 0 ]]; then
        while IFS= read -r iface; do
            ITYPE=$(echo "$iface" | jq -r '.type // "0"')
            IAVAIL=$(echo "$iface" | jq -r '.available // "MISSING"')
            IFACE_ID=$(echo "$iface" | jq -r '.interfaceid // "?"')
            case "$ITYPE" in
                1) AGENT_TYPES_ARR+=("Zabbix Agent") ;;
                2) AGENT_TYPES_ARR+=("SNMP") ;;
                3) AGENT_TYPES_ARR+=("IPMI") ;;
                4) AGENT_TYPES_ARR+=("JMX") ;;
            esac
            TRACE+="[Step2] iface#${IFACE_ID} type=${ITYPE} available=${IAVAIL}"$'\n'
        done < <(echo "$host" | jq -c '.interfaces[]? // empty')
    else
        TRACE+="[Step2] Không có interface"$'\n'
    fi

    # Step 3: semantic từ group + template names
    GROUPS=$(echo "$host" | jq -r '[.groups[]?.name] | join("|")' | tr '[:upper:]' '[:lower:]')
    TEMPLATES=$(echo "$host" | jq -r '[.parentTemplates[]?.name] | join("|")' | tr '[:upper:]' '[:lower:]')
    ALL_NAMES="$GROUPS|$TEMPLATES"

    SEMANTIC_TYPES=()
    echo "$ALL_NAMES" | grep -qiE "http agent|dahua|hikvision" && SEMANTIC_TYPES+=("HTTP Agent")
    echo "$ALL_NAMES" | grep -qiE "zabbix agent|windows|linux by zabbix" && SEMANTIC_TYPES+=("Zabbix Agent")
    echo "$ALL_NAMES" | grep -qiE "snmp|printer" && SEMANTIC_TYPES+=("SNMP")
    echo "$ALL_NAMES" | grep -qiE "ipmi|idrac|ilo" && SEMANTIC_TYPES+=("IPMI")
    echo "$ALL_NAMES" | grep -qiE "jmx" && SEMANTIC_TYPES+=("JMX")
    echo "$ALL_NAMES" | grep -qiE "active" && SEMANTIC_TYPES+=("Active Agent")

    if [[ ${#SEMANTIC_TYPES[@]} -gt 0 ]]; then
        AGENT_TYPES_ARR=("${SEMANTIC_TYPES[@]}")
        TRACE+="[Step3] Semantic override → ${SEMANTIC_TYPES[*]}"$'\n'
    else
        TRACE+="[Step3] Không có keyword semantic nào khớp"$'\n'
    fi

    # Step 4: fallback
    if [[ ${#AGENT_TYPES_ARR[@]} -eq 0 ]]; then
        AGENT_TYPES_ARR=("HTTP Agent")
        TRACE+="[Step4] Fallback → HTTP Agent"$'\n'
    fi

    # Dedup agent types
    mapfile -t AGENT_TYPES_DEDUP < <(printf '%s\n' "${AGENT_TYPES_ARR[@]}" | sort -u)
    PROTOCOLS="${AGENT_TYPES_DEDUP[*]}"

    # ── Lọc theo protocol ─────────────────────────────────────────────────
    if [[ -n "$FILTER_PROTOCOL" ]]; then
        if ! echo "$PROTOCOLS" | grep -qi "$FILTER_PROTOCOL"; then continue; fi
    fi

    # ── Tính availability ─────────────────────────────────────────────────
    # Từ interface
    AVAIL_VALUES=("$AVAIL_AGENT" "$AVAIL_SNMP" "$AVAIL_IPMI" "$AVAIL_JMX")
    while IFS= read -r iface; do
        IA=$(echo "$iface" | jq -r '.available // "0"')
        AVAIL_VALUES+=("$IA")
    done < <(echo "$host" | jq -c '.interfaces[]? // empty')

    # Composite resolution
    HAS_ONE=false; ALL_DOWN=true; HAS_NONZERO=false
    for v in "${AVAIL_VALUES[@]}"; do
        [[ "$v" == "1" ]] && HAS_ONE=true && HAS_NONZERO=true
        [[ "$v" != "0" && "$v" != "2" ]] || true
        [[ "$v" == "1" || "$v" == "2" ]] && HAS_NONZERO=true
        [[ "$v" == "1" ]] || true
        [[ "$v" != "2" ]] && ALL_DOWN=false || true
    done

    AVAIL_CODE=0
    if $HAS_ONE; then
        AVAIL_CODE=1
    elif $HAS_NONZERO && ! $HAS_ONE; then
        AVAIL_CODE=2
    fi

    # HTTP Agent: thêm item state check
    IS_HTTP=false
    echo "$PROTOCOLS" | grep -qi "HTTP Agent\|Active" && IS_HTTP=true

    ITEM_CHECK="Không áp dụng"
    if $IS_HTTP || [[ $AVAIL_CODE -eq 0 ]]; then
        # Đếm items của host này
        HOST_ITEMS=$(echo "$ITEM_RESP" | jq -c --arg hid "$HOST_ID" '.result[] | select(.hostid==$hid)')
        TOTAL_HOST_ITEMS=$(echo "$HOST_ITEMS" | grep -c '"hostid"' || true)
        NORMAL_ITEMS=$(echo "$HOST_ITEMS" | jq -r '.state' 2>/dev/null | grep -c "^0$" || true)
        BROKEN_ITEMS=$(echo "$HOST_ITEMS" | jq -r '.state' 2>/dev/null | grep -c "^1$" || true)
        ITEM_ERR_SAMPLE=$(echo "$HOST_ITEMS" | jq -r 'select(.state=="1") | .error // ""' 2>/dev/null | head -1 || echo "")

        if [[ $TOTAL_HOST_ITEMS -eq 0 ]]; then
            ITEM_CHECK="Không có item → Unknown"
            [[ $AVAIL_CODE -eq 0 ]] && AVAIL_CODE=0
        elif [[ $NORMAL_ITEMS -gt 0 ]]; then
            ITEM_CHECK="Items: ${NORMAL_ITEMS} bình thường / ${BROKEN_ITEMS} lỗi"
            [[ $AVAIL_CODE -eq 0 ]] && AVAIL_CODE=1  # Override Unknown → Available
        else
            ITEM_CHECK="Items: TẤT CẢ lỗi (${BROKEN_ITEMS})"
            [[ $AVAIL_CODE -eq 0 ]] && AVAIL_CODE=2  # Override Unknown → Unavailable
        fi
        TRACE+="[Item] total=${TOTAL_HOST_ITEMS} normal=${NORMAL_ITEMS} broken=${BROKEN_ITEMS}"$'\n'
        [[ -n "$ITEM_ERR_SAMPLE" ]] && TRACE+="[Item] Lỗi mẫu: ${ITEM_ERR_SAMPLE}"$'\n'
    fi

    # Label
    case $AVAIL_CODE in
        0) AVAIL_LABEL="${YELLOW}Unknown${NC}"  ;;
        1) AVAIL_LABEL="${GREEN}Available${NC}" ;;
        2) AVAIL_LABEL="${RED}Unavailable${NC}";;
    esac

    # ── Bộ đếm ────────────────────────────────────────────────────────────
    case $AVAIL_CODE in
        0) ((CNT_UNKNOWN++))     ;;
        1) ((CNT_AVAILABLE++))   ;;
        2) ((CNT_UNAVAILABLE++)) ;;
    esac
    [[ $MAINT -eq 1 ]] && ((CNT_MAINT++))
    [[ -n "$ZABBIX_ERR" ]] && ((CNT_ERROR++))
    echo "$PROTOCOLS" | grep -qi "Zabbix Agent" && ((CNT_ZABBIX_AGENT++)) || true
    echo "$PROTOCOLS" | grep -qi "HTTP Agent"   && ((CNT_HTTP_AGENT++))   || true
    echo "$PROTOCOLS" | grep -qi "SNMP"         && ((CNT_SNMP++))         || true
    echo "$PROTOCOLS" | grep -qi "IPMI"         && ((CNT_IPMI++))         || true
    echo "$PROTOCOLS" | grep -qi "JMX"          && ((CNT_JMX++))          || true
    echo "$PROTOCOLS" | grep -qi "Active"       && ((CNT_ACTIVE++))       || true
    [[ ${#AGENT_TYPES_DEDUP[@]} -eq 0 ]] && ((CNT_UNRESOLVED++)) || true

    # ── In thông tin host ─────────────────────────────────────────────────
    if ! $SUMMARY_ONLY; then
        echo ""
        echo -e "────────────────────────────────────────────────────────"
        echo -e "${BOLD}Host:${NC} $HOST_NAME  ${BLUE}id=$HOST_ID${NC}  ip=${PRIMARY_IP:-—}$([ $MAINT -eq 1 ] && echo -e " ${YELLOW}[MAINTENANCE]${NC}" || true)"
        echo -e "  Trạng thái  : $(echo -e "$AVAIL_LABEL")"
        echo -e "  Giao thức   : ${BOLD}$PROTOCOLS${NC}"
        echo -e "  Interfaces  : $IFACE_COUNT (types: ${IFACE_TYPES:-—})"
        echo -e "  Items check : $ITEM_CHECK"
        [[ -n "$ZABBIX_ERR" ]] && echo -e "  ${RED}Zabbix lỗi${NC}  : $ZABBIX_ERR"

        if $VERBOSE; then
            echo -e "  ${CYAN}Detection trace:${NC}"
            while IFS= read -r line; do
                [[ -n "$line" ]] && echo -e "    ${CYAN}▸${NC} $line"
            done <<< "$TRACE"

            # Raw interface data
            if [[ $IFACE_COUNT -gt 0 ]]; then
                echo -e "  ${CYAN}Raw interfaces:${NC}"
                echo "$host" | jq -r '.interfaces[] |
                    "    #\(.interfaceid) type=\(.type) ip=\(.ip) port=\(.port) available=\(.available // "MISSING") main=\(.main)"'
            fi

            # Groups + Templates
            GNAMES=$(echo "$host" | jq -r '[.groups[].name] | join(", ")')
            TNAMES=$(echo "$host" | jq -r '[.parentTemplates[].name] | join(", ")')
            [[ -n "$GNAMES" ]] && echo -e "  ${CYAN}Groups${NC}    : $GNAMES"
            [[ -n "$TNAMES" ]] && echo -e "  ${CYAN}Templates${NC} : $TNAMES"
        fi
    fi

    # ── Lưu JSON cho export ───────────────────────────────────────────────
    REPORT_ENTRIES+=("$(jq -cn \
        --arg hostid "$HOST_ID" \
        --arg name "$HOST_NAME" \
        --arg ip "${PRIMARY_IP:-}" \
        --arg protocols "$PROTOCOLS" \
        --arg avail_label "$([ $AVAIL_CODE -eq 1 ] && echo Available || ([ $AVAIL_CODE -eq 2 ] && echo Unavailable || echo Unknown))" \
        --argjson avail_code "$AVAIL_CODE" \
        --argjson maint "$MAINT" \
        --arg item_check "$ITEM_CHECK" \
        --arg zabbix_error "$ZABBIX_ERR" \
        --arg trace "$TRACE" \
        '{hostid:$hostid,name:$name,ip:$ip,protocols:$protocols,available_code:$avail_code,
          available_label:$avail_label,in_maintenance:($maint=="1"),item_check:$item_check,
          zabbix_error:$zabbix_error,trace:$trace}')")

done <<< "$HOSTS_JSON"

# ─── BƯỚC 6: PHÂN TÍCH CÁC HOST CÓ VẤN ĐỀ ──────────────────────────────
log_section "BƯỚC 6: PHÂN TÍCH CÁC VẤN ĐỀ PHỔ BIẾN"

PROBLEM_COUNT=0

# 6a. Host không có interfaces VÀ không có items
while IFS= read -r host; do
    HOST_ID=$(echo "$host" | jq -r '.hostid')
    HOST_NAME=$(echo "$host" | jq -r '.name // .host')
    IFACE_COUNT=$(echo "$host" | jq '.interfaces | length // 0')
    ITEM_COUNT=$(echo "$ITEM_RESP" | jq --arg hid "$HOST_ID" '[.result[] | select(.hostid==$hid)] | length')

    if [[ $IFACE_COUNT -eq 0 && $ITEM_COUNT -eq 0 ]]; then
        log_warn "Host ${BOLD}$HOST_NAME${NC} (id=$HOST_ID) — Không có interface VÀ không có item → Không thể xác định trạng thái!"
        ((PROBLEM_COUNT++)) || true
    fi
done <<< "$HOSTS_JSON"

# 6b. Host có Zabbix error
while IFS= read -r host; do
    ZERR=$(echo "$host" | jq -r '.error // ""')
    [[ -z "$ZERR" ]] && continue
    HOST_NAME=$(echo "$host" | jq -r '.name // .host')
    HOST_ID=$(echo "$host" | jq -r '.hostid')
    log_error "Host ${BOLD}$HOST_NAME${NC} (id=$HOST_ID) — Zabbix báo lỗi: $ZERR"
    ((PROBLEM_COUNT++)) || true
done <<< "$HOSTS_JSON"

# 6c. HTTP Agent host có TẤT CẢ items broken
while IFS= read -r host; do
    HOST_ID=$(echo "$host" | jq -r '.hostid')
    HOST_NAME=$(echo "$host" | jq -r '.name // .host')
    GROUPS=$(echo "$host" | jq -r '[.groups[].name, .parentTemplates[].name] | join("|")' | tr '[:upper:]' '[:lower:]')
    IFACE_COUNT=$(echo "$host" | jq '.interfaces | length // 0')

    # Chỉ kiểm tra HTTP Agent hosts (không có interface thật)
    if ! echo "$GROUPS" | grep -qiE "http.agent|dahua|hikvision" && [[ $IFACE_COUNT -gt 0 ]]; then
        continue
    fi

    BROKEN=$(echo "$ITEM_RESP" | jq --arg hid "$HOST_ID" \
        '[.result[] | select(.hostid==$hid and .state=="1")] | length')
    TOTAL=$(echo "$ITEM_RESP" | jq --arg hid "$HOST_ID" \
        '[.result[] | select(.hostid==$hid)] | length')

    if [[ $TOTAL -gt 0 && $BROKEN -eq $TOTAL ]]; then
        SAMPLE_ERR=$(echo "$ITEM_RESP" | jq -r --arg hid "$HOST_ID" \
            '[.result[] | select(.hostid==$hid and .state=="1")] | first | .error // "Không rõ"')
        log_error "HTTP Agent ${BOLD}$HOST_NAME${NC} — ${BROKEN}/${TOTAL} items lỗi"
        log_sub   "Lỗi mẫu: $SAMPLE_ERR"
        ((PROBLEM_COUNT++)) || true
    fi
done <<< "$HOSTS_JSON"

# 6d. Cấu hình backend: kiểm tra ZABBIX_ENABLED
if [[ -f "$ENV_FILE" ]]; then
    ZABBIX_ENABLED=$(grep -E "^ZABBIX_ENABLED" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' || echo "true")
    if [[ "$ZABBIX_ENABLED" == "false" ]]; then
        log_error "ZABBIX_ENABLED=false trong $ENV_FILE → Backend đang bị tắt!"
        ((PROBLEM_COUNT++)) || true
    else
        log_ok "ZABBIX_ENABLED=$ZABBIX_ENABLED"
    fi
fi

[[ $PROBLEM_COUNT -eq 0 ]] && log_ok "Không phát hiện vấn đề cấu hình nào"

# ─── BƯỚC 7: SUMMARY ─────────────────────────────────────────────────────
log_section "BƯỚC 7: TỔNG KẾT"

echo -e "\n${BOLD}Tổng số host được giám sát:${NC} $TOTAL_HOSTS"
echo ""
echo -e "  Trạng thái kết nối:"
echo -e "    ${GREEN}✓ Hoạt động (Available)${NC}        : $CNT_AVAILABLE"
echo -e "    ${RED}✗ Không hoạt động (Unavailable)${NC} : $CNT_UNAVAILABLE"
echo -e "    ${YELLOW}? Không rõ (Unknown)${NC}            : $CNT_UNKNOWN"
[[ $CNT_MAINT -gt 0 ]] && \
echo -e "    ${YELLOW}🔧 Đang bảo trì${NC}                 : $CNT_MAINT"
[[ $CNT_ERROR -gt 0 ]] && \
echo -e "    ${RED}⚠ Có lỗi Zabbix${NC}                : $CNT_ERROR"

echo ""
echo -e "  Phân loại giao thức:"
[[ $CNT_ZABBIX_AGENT -gt 0 ]] && echo -e "    ${BLUE}Zabbix Agent${NC}    : $CNT_ZABBIX_AGENT"
[[ $CNT_HTTP_AGENT   -gt 0 ]] && echo -e "    ${CYAN}HTTP Agent${NC}      : $CNT_HTTP_AGENT"
[[ $CNT_SNMP         -gt 0 ]] && echo -e "    ${CYAN}SNMP${NC}            : $CNT_SNMP"
[[ $CNT_IPMI         -gt 0 ]] && echo -e "    ${YELLOW}IPMI${NC}            : $CNT_IPMI"
[[ $CNT_JMX          -gt 0 ]] && echo -e "    ${YELLOW}JMX${NC}             : $CNT_JMX"
[[ $CNT_ACTIVE       -gt 0 ]] && echo -e "    ${BLUE}Active Agent${NC}    : $CNT_ACTIVE"
[[ $CNT_UNRESOLVED   -gt 0 ]] && \
echo -e "    ${RED}KHÔNG XÁC ĐỊNH  : $CNT_UNRESOLVED${NC} ← CẦN KIỂM TRA!"

# Tổng vấn đề
echo ""
if [[ $PROBLEM_COUNT -gt 0 ]]; then
    echo -e "${RED}${BOLD}⚠ Phát hiện $PROBLEM_COUNT vấn đề cần xem xét!${NC}"
    echo -e "  → Chạy với ${BOLD}--verbose${NC} để xem trace chi tiết từng host"
    echo -e "  → Dùng ${BOLD}--protocol 'HTTP Agent'${NC} để lọc theo giao thức"
else
    echo -e "${GREEN}${BOLD}✓ Không phát hiện vấn đề nào.${NC}"
fi

echo -e "\n${BOLD}Tổng items được lấy:${NC} $TOTAL_ITEMS"

# ─── Xuất JSON nếu cần ───────────────────────────────────────────────────
if [[ -n "$OUTPUT_FILE" ]]; then
    printf '%s\n' "${REPORT_ENTRIES[@]}" | jq -s '.' > "$OUTPUT_FILE"
    log_ok "Kết quả JSON đã ghi vào: ${BOLD}$OUTPUT_FILE${NC}"
fi

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "  Hoàn thành chẩn đoán lúc $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
