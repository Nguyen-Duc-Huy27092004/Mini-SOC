#!/bin/bash

# ============================================================
# Mini-SOC Wazuh Connection Diagnostics
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

echo ""
log_section "WAZUH CONNECTION DIAGNOSTICS"

# ============================================================
# 1. CHECK ENVIRONMENT CONFIGURATION
# ============================================================

log_section "1. KIỂM TRA CẤU HÌNH MÔIT TRƯỜNG"

if [ ! -f ".env.production" ]; then
    log_error ".env.production KHÔNG TỒN TẠI!"
    log_warn "Bạn cần tạo file .env.production với các biến cấu hình"
    echo ""
else
    log_success ".env.production tìm thấy"
    
    # Check critical Wazuh variables
    WAZUH_API_URL=$(grep "^WAZUH_API_URL=" .env.production 2>/dev/null | cut -d'=' -f2 | tr -d '"' | sed 's/^//')
    WAZUH_API_USER=$(grep "^WAZUH_API_USER=" .env.production 2>/dev/null | cut -d'=' -f2 | tr -d '"')
    WAZUH_API_PASSWORD=$(grep "^WAZUH_API_PASSWORD=" .env.production 2>/dev/null | cut -d'=' -f2 | tr -d '"')
    WAZUH_ALERTS_FILE=$(grep "^WAZUH_ALERTS_FILE=" .env.production 2>/dev/null | cut -d'=' -f2 | tr -d '"')
    WAZUH_VERIFY_SSL=$(grep "^WAZUH_VERIFY_SSL=" .env.production 2>/dev/null | cut -d'=' -f2 | tr -d '"')
    
    echo ""
    echo "WAZUH Configuration:"
    echo "  WAZUH_API_URL: ${WAZUH_API_URL:-NOT SET}"
    echo "  WAZUH_API_USER: ${WAZUH_API_USER:-NOT SET}"
    echo "  WAZUH_API_PASSWORD: $([ -z "$WAZUH_API_PASSWORD" ] && echo 'NOT SET' || echo '✓ SET')"
    echo "  WAZUH_ALERTS_FILE: ${WAZUH_ALERTS_FILE:-NOT SET}"
    echo "  WAZUH_VERIFY_SSL: ${WAZUH_VERIFY_SSL:-NOT SET}"
    echo ""
    
    # Validate Wazuh configuration
    if [ -z "$WAZUH_API_URL" ]; then
        log_error "WAZUH_API_URL không được cấu hình!"
    elif [ -z "$WAZUH_API_PASSWORD" ]; then
        log_error "WAZUH_API_PASSWORD không được cấu hình!"
    elif [ -z "$WAZUH_ALERTS_FILE" ]; then
        log_error "WAZUH_ALERTS_FILE không được cấu hình (NGUYÊN NHÂN CHÍNH)!"
        log_warn "Collector service được TẮT vì thiếu đường dẫn file alerts"
    else
        log_success "Cấu hình Wazuh có vẻ OK"
    fi
fi

# ============================================================
# 2. CHECK DOCKER CONTAINERS
# ============================================================

log_section "2. KIỂM TRA DOCKER CONTAINERS"

if ! command -v docker &> /dev/null; then
    log_error "Docker không cài đặt!"
    exit 1
fi

# Check if containers are running
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "mini_soc|wazuh" || log_warn "Không có container nào chạy"

echo ""

# Check backend logs
if docker ps -a | grep -q "mini_soc.*backend"; then
    log_info "Checking backend logs for Wazuh connection errors..."
    echo ""
    docker logs mini_soc_backend 2>&1 | tail -50 | grep -E "collector|WAZUH|connection" || log_warn "Không tìm thấy thông báo Wazuh trong logs"
    echo ""
fi

# ============================================================
# 3. CHECK WAZUH ALERTS FILE ON HOST
# ============================================================

log_section "3. KIỂM TRA FILE ALERTS CỦA WAZUH"

if [ -d "/var/ossec/logs/alerts" ]; then
    log_success "Thư mục Wazuh alerts tìm thấy: /var/ossec/logs/alerts"
    ls -lah /var/ossec/logs/alerts/
    echo ""
    
    if [ -f "/var/ossec/logs/alerts/alerts.json" ]; then
        log_success "File alerts.json tìm thấy"
        log_info "Sample alerts (last 3 lines):"
        tail -3 /var/ossec/logs/alerts/alerts.json
    else
        log_warn "File alerts.json KHÔNG TỒN TẠI"
    fi
else
    log_warn "Thư mục /var/ossec/logs/alerts KHÔNG TỒN TẠI"
    log_info "Đây có thể là bởi:"
    log_info "  1. Wazuh chưa được cài đặt trên server này"
    log_info "  2. Wazuh cài đặt ở vị trí khác"
fi

echo ""

# ============================================================
# 4. CHECK WAZUH API CONNECTIVITY
# ============================================================

log_section "4. KIỂM TRA KẾT NỐI WAZUH API"

if [ -z "$WAZUH_API_URL" ]; then
    log_warn "WAZUH_API_URL không được cấu hình, bỏ qua kiểm tra"
else
    log_info "Testing API at: $WAZUH_API_URL"
    
    # Try HTTPS first, then HTTP
    if curl -s -k -u "$WAZUH_API_USER:$WAZUH_API_PASSWORD" -X GET "$WAZUH_API_URL/api/summary" -H "Content-Type: application/json" 2>/dev/null | grep -q "agents"; then
        log_success "Kết nối WAZUH API thành công!"
        
        # Get manager status
        MANAGER_STATUS=$(curl -s -k -u "$WAZUH_API_USER:$WAZUH_API_PASSWORD" -X GET "$WAZUH_API_URL/api/summary" -H "Content-Type: application/json" 2>/dev/null)
        echo "$MANAGER_STATUS" | jq . 2>/dev/null || echo "$MANAGER_STATUS"
    else
        log_error "KHÔNG THỂ KẾT NỐI WAZUH API!"
        log_warn "Kiểm tra:"
        log_warn "  1. URL Wazuh API có đúng không?"
        log_warn "  2. Username/password có chính xác không?"
        log_warn "  3. Wazuh server có chạy không?"
    fi
fi

# ============================================================
# 5. DOCKER MOUNT VERIFICATION
# ============================================================

log_section "5. KIỂM TRA DOCKER MOUNT VOLUMES"

if docker ps | grep -q "mini_soc.*backend"; then
    log_info "Checking mounted volumes in backend container..."
    docker inspect mini_soc_backend 2>/dev/null | jq '.[] | .Mounts[] | {Source: .Source, Destination: .Destination, Mode: .Mode}' 2>/dev/null || log_warn "Cannot inspect container mounts"
fi

# ============================================================
# 6. RECOMMENDATIONS
# ============================================================

log_section "KHUYẾN NGHỊ XỬ LÝ"

echo "Để khắc phục vấn đề 'Mất kết nối', bạn cần:"
echo ""
echo "1️⃣  CẤU HÌNH BIẾN MÔI TRƯỜNG:"
echo "   cd $(pwd)"
echo "   # Cập nhật/tạo .env.production với:"
echo ""
echo "   WAZUH_API_URL=https://YOUR_WAZUH_IP:55000"
echo "   WAZUH_API_USER=wazuh"
echo "   WAZUH_API_PASSWORD=YOUR_WAZUH_PASSWORD"
echo "   WAZUH_ALERTS_FILE=/var/ossec/logs/alerts/alerts.json"
echo "   WAZUH_VERIFY_SSL=false"
echo ""

echo "2️⃣  MOUNT VOLUME WAZUH VÀO CONTAINER:"
echo "   Thêm vào docker-compose.production.yml backend service:"
echo ""
echo "   volumes:"
echo "     - /var/ossec/logs/alerts:/var/ossec/logs/alerts:ro"
echo ""

echo "3️⃣  RESTART DOCKER:"
echo "   docker-compose -f docker-compose.production.yml down"
echo "   docker-compose -f docker-compose.production.yml up -d"
echo ""

echo "4️⃣  KIỂM TRA LOGS:"
echo "   docker logs -f mini_soc_backend | grep -E 'collector|WAZUH|connection'"
echo ""

log_success "Chạy script này lại sau khi cấu hình để xác nhận kết nối"
