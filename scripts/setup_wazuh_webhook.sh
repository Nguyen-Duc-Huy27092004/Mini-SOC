#!/bin/bash
# ==============================================================================
# Tự động cấu hình Webhook cho Wazuh Manager đẩy log về Mini-SOC
# ==============================================================================

# Kiểm tra quyền root
if [ "$EUID" -ne 0 ]; then
  echo "[LỖI] Vui lòng chạy script này dưới quyền root (sudo)."
  exit 1
fi

OSSEC_CONF="/var/ossec/etc/ossec.conf"
MINI_SOC_IP=$1

if [ -z "$MINI_SOC_IP" ]; then
  echo "Sử dụng: $0 <IP_MINI_SOC>"
  echo "Ví dụ: $0 192.168.1.100"
  exit 1
fi

if [ ! -f "$OSSEC_CONF" ]; then
  echo "[LỖI] Không tìm thấy file cấu hình Wazuh tại $OSSEC_CONF."
  echo "Bạn có đang chạy script này trên server chứa Wazuh Manager không?"
  exit 1
fi

# Kiểm tra xem webhook đã tồn tại chưa
if grep -q "custom-webhook" "$OSSEC_CONF"; then
  echo "[LỖI] Cấu hình Webhook 'custom-webhook' có vẻ đã được cấu hình trong ossec.conf."
  echo "Vui lòng mở file $OSSEC_CONF ra và kiểm tra tay."
  exit 1
fi

# Tạo đoạn block XML cần thiết, thủ thuật là thay thế thẻ đóng cuối cùng
WEBHOOK_XML="
  <integration>
    <name>custom-webhook</name>
    <hook_url>http://${MINI_SOC_IP}:8000/api/v1/wazuh/webhook</hook_url>
    <level>3</level>
    <alert_format>json</alert_format>
  </integration>
</ossec_config>"

# Backup cấu hình cũ đề phòng rủi ro
BACKUP_FILE="${OSSEC_CONF}.bak_$(date +%s)"
cp "$OSSEC_CONF" "$BACKUP_FILE"
echo "[INFO] Đã sao lưu $OSSEC_CONF ra file backup $BACKUP_FILE"

# Dùng sed thay thế dòng chứa </ossec_config> thành block tích hợp và thẻ đóng
sed -i "s|</ossec_config>|$WEBHOOK_XML|g" "$OSSEC_CONF"

echo "[INFO] Đã tiêm cấu hình Webhook thành công vào $OSSEC_CONF."
echo "[INFO] Đang khởi động lại Wazuh Manager để áp dụng..."
systemctl restart wazuh-manager

echo "=============================================================================="
echo "[THÀNH CÔNG] Wazuh sẽ tự động bắn cảnh báo JSON (level 3 trở lên) về:"
echo "http://${MINI_SOC_IP}:8000/api/v1/wazuh/webhook"
echo "=============================================================================="
