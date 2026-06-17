# 🔍 HƯỚNG DẪN CHẨN ĐOÁN API CONNECTIVITY

## 🎯 MỤC ĐÍCH

Xác định chính xác nguyên nhân hệ thống không nhận được dữ liệu:
- ❓ **Wazuh API** không hoạt động?
- ❓ **Zabbix API** không hoạt động?
- ❓ **Hệ thống Mini-SOC** có vấn đề?
- ❓ **Cấu hình** sai?

---

## 🚀 CÁCH SỬ DỤNG

### Trên Server (Linux)

```bash
# 1. Vào thư mục deployment
cd /opt/mini-soc

# 2. Chạy script chẩn đoán
chmod +x diagnose_api_connectivity.sh
sudo bash diagnose_api_connectivity.sh
```

### Trên Máy Local (Windows)

```powershell
# 1. Mở PowerShell
cd C:\Path\To\Mini-SOC

# 2. Chạy script
powershell -ExecutionPolicy Bypass -File Diagnose-APIConnectivity.ps1
```

---

## 📊 SCRIPT SẼ KIỂM TRA

### ✅ BƯỚC 1: Đọc Cấu Hình
- Đọc từ `.env.production` hoặc `backend/.env`
- Hiển thị WAZUH_API_URL, ZABBIX_API_URL
- Hiển thị credentials (ẩn password)

### ✅ BƯỚC 2: Kiểm Tra Wazuh API

**Test 1: Network Connectivity**
- Ping Wazuh host
- Kết quả: Host có reachable không?

**Test 2: Port Connectivity**
- Test kết nối TCP tới port 55000
- Kết quả: Port có mở không?

**Test 3: HTTPS/TLS**
- Test HTTPS connection
- Kết quả: SSL/TLS có hoạt động không?

**Test 4: Authentication**
- Gửi request authentication với credentials
- Nhận JWT token
- Kết quả: Credentials có đúng không?

**Test 5: Get Agents**
- Gọi API `/agents`
- Kết quả: Wazuh có trả về danh sách agents không?

### ✅ BƯỚC 3: Kiểm Tra Zabbix API

**Test 1: HTTP Connectivity**
- Gọi Zabbix API endpoint
- Kết quả: Endpoint có accessible không?

**Test 2: Authentication**
- Login với JSON-RPC
- Nhận auth token
- Kết quả: Credentials có đúng không?

**Test 3: Get Hosts**
- Gọi API `host.get`
- Kết quả: Zabbix có trả về hosts không?

### ✅ BƯỚC 4: Kiểm Tra Backend

- Container có đang chạy không?
- Logs có lỗi Wazuh connection không?
- Logs có lỗi Zabbix connection không?
- Collector có khởi động không?
- Collector có xử lý events không?

### ✅ BƯỚC 5: Kiểm Tra Database

- Container có chạy không?
- Có bao nhiêu wazuh_events?
- Event mới nhất là gì?
- Có bao nhiêu agents trong endpoint_inventory?

### ✅ BƯỚC 6: Kiểm Tra Wazuh Alerts File

- File `/var/ossec/logs/alerts/alerts.json` có tồn tại không?
- File có dữ liệu không (size > 0)?
- Dòng cuối cùng trong file là gì?
- Volume mount có đúng không?

---

## 📋 KẾT QUẢ CÓ THỂ

### ✅ Kịch bản 1: Wazuh API OK, Có Dữ Liệu

```
╔════════════════════════════════════════════════╗
║              KẾT LUẬN                          ║
╚════════════════════════════════════════════════╝

✓ HỆ THỐNG HOẠT ĐỘNG BÌNH THƯỜNG

Wazuh API hoạt động và hệ thống đã thu thập 150 events.
Dashboard sẽ hiển thị dữ liệu.
```

**→ Không có vấn đề!**

### ⚠️ Kịch bản 2: Wazuh API OK, Chưa Có Dữ Liệu

```
╔════════════════════════════════════════════════╗
║              KẾT LUẬN                          ║
╚════════════════════════════════════════════════╝

⚠ WAZUH API HOẠT ĐỘNG NHƯNG CHƯA CÓ DỮ LIỆU

NGUYÊN NHÂN:
  - Wazuh API hoạt động tốt
  - Nhưng chưa có alerts trong database

CÓ THỂ DO:
  1. Wazuh alerts file trống (Wazuh chưa tạo alerts)
  2. Volume mount không đúng
  3. Collector chưa xử lý alerts

GIẢI PHÁP:
  1. Inject test data để test UI:
     bash fix_data_flow_complete.sh
  2. Kiểm tra Wazuh có agents kết nối:
     /var/ossec/bin/agent_control -l
  3. Kiểm tra Wazuh alerts file:
     tail -f /var/ossec/logs/alerts/alerts.json
```

**→ Wazuh hoạt động, nhưng chưa có alerts thật**

### ❌ Kịch bản 3: Wazuh API Không Hoạt Động - Port Closed

```
1. WAZUH API
   Status: PORT_CLOSED
   ✗ Wazuh API port không mở
   → Wazuh service KHÔNG CHẠY hoặc firewall chặn
   Error: Port 55000 không mở hoặc firewall chặn

╔════════════════════════════════════════════════╗
║              KẾT LUẬN                          ║
╚════════════════════════════════════════════════╝

✗ LỖI TỪ WAZUH API

NGUYÊN NHÂN: Wazuh API không hoạt động
LỖI: Port 55000 không mở

GIẢI PHÁP:
  1. Kiểm tra Wazuh service: systemctl status wazuh-manager
  2. Start Wazuh nếu chưa chạy: systemctl start wazuh-manager
  3. Kiểm tra firewall: ufw status
```

**→ Wazuh service không chạy!**

### ❌ Kịch bản 4: Wazuh API - Invalid Credentials

```
1. WAZUH API
   Status: INVALID_CREDENTIALS
   ✗ Credentials sai
   → Kiểm tra WAZUH_API_USER và WAZUH_API_PASSWORD

╔════════════════════════════════════════════════╗
║              KẾT LUẬN                          ║
╚════════════════════════════════════════════════╝

✗ LỖI TỪ WAZUH API

NGUYÊN NHÂN: Wazuh API không hoạt động
LỖI: Username hoặc password sai

GIẢI PHÁP:
  1. Kiểm tra credentials trong .env.production
  2. Lấy password đúng từ Wazuh:
     cat /var/ossec/.secret
  3. Hoặc reset password trong Wazuh dashboard
```

**→ Credentials sai!**

### ❌ Kịch bản 5: Wazuh API - Not Configured

```
1. WAZUH API
   Status: NOT_CONFIGURED
   ✗ Wazuh API chưa được cấu hình
   → Cần cấu hình WAZUH_API_URL trong .env

GIẢI PHÁP:
  1. Cấu hình WAZUH_API_URL trong .env.production
  2. Format: https://<IP>:55000
  3. Restart containers
```

**→ Chưa cấu hình!**

---

## 🔧 GIẢI PHÁP CHO CÁC VẤN ĐỀ THƯỜNG GẶP

### 1. Wazuh Service Không Chạy

**Triệu chứng**:
- Status: PORT_CLOSED
- Cannot connect to port 55000

**Kiểm tra**:
```bash
# Trên server Wazuh
systemctl status wazuh-manager
```

**Sửa**:
```bash
# Start Wazuh
systemctl start wazuh-manager

# Enable auto-start
systemctl enable wazuh-manager

# Kiểm tra lại
systemctl status wazuh-manager
```

### 2. Credentials Sai

**Triệu chứng**:
- Status: INVALID_CREDENTIALS
- Authentication failed

**Lấy password đúng**:
```bash
# Trên server Wazuh

# Option 1: Từ file secret
cat /var/ossec/.secret

# Option 2: Từ API credentials
cat /var/ossec/api/configuration/security/users.yml

# Option 3: Reset password qua Wazuh dashboard
```

**Cập nhật vào .env.production**:
```bash
vim /opt/mini-soc/.env.production

# Sửa dòng:
WAZUH_API_PASSWORD=<password-mới-lấy-được>

# Restart containers
docker compose -f docker-compose.production.yml restart backend
```

### 3. Firewall Chặn

**Triệu chứng**:
- Cannot ping host
- Port timeout

**Kiểm tra firewall trên server Wazuh**:
```bash
# Check ufw
ufw status

# Check iptables
iptables -L -n | grep 55000
```

**Mở port**:
```bash
# UFW
ufw allow 55000/tcp
ufw reload

# Iptables
iptables -A INPUT -p tcp --dport 55000 -j ACCEPT
```

### 4. Wazuh Chưa Có Alerts

**Triệu chứng**:
- Wazuh API OK
- Database có 0 events
- Alerts file rỗng

**Kiểm tra**:
```bash
# Xem alerts file
tail -f /var/ossec/logs/alerts/alerts.json

# Kiểm tra agents
/var/ossec/bin/agent_control -l

# Kiểm tra rules
/var/ossec/bin/wazuh-logtest
```

**Giải pháp tạm thời**:
```bash
# Inject test data vào Mini-SOC
cd /opt/mini-soc
bash fix_data_flow_complete.sh
# Chọn "yes" khi hỏi về test data
```

### 5. Volume Mount Sai

**Triệu chứng**:
- Alerts file không tồn tại trong container
- Collector không tìm thấy file

**Kiểm tra**:
```bash
# Xem volume mounts
docker inspect mini_soc_backend_prod | grep -A 10 "Mounts"

# Kiểm tra trong container
docker exec mini_soc_backend_prod ls -la /var/ossec/logs/alerts/
```

**Sửa trong .env.production**:
```bash
# Đúng đường dẫn trên server Wazuh
WAZUH_ALERTS_HOST_PATH=/var/ossec/logs/alerts

# Restart
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d
```

### 6. Zabbix Không Hoạt Động

**Nếu không dùng Zabbix**:
```bash
# Disable trong .env.production
ZABBIX_ENABLED=false

# Restart
docker compose restart backend
```

**Nếu muốn dùng Zabbix**:
- Kiểm tra Zabbix service: `systemctl status zabbix-server`
- Kiểm tra Zabbix web interface accessible
- Kiểm tra credentials
- Set `ZABBIX_ENABLED=true`

---

## 📊 EXAMPLE OUTPUT

```bash
$ sudo bash diagnose_api_connectivity.sh

========================================
 BƯỚC 1: Thu thập thông tin cấu hình
========================================

[INFO] Đọc cấu hình từ .env.production...
[✓] Đã đọc cấu hình từ: .env.production
[INFO] Cấu hình hiện tại:
  WAZUH_API_URL     : https://192.168.10.4:55000
  WAZUH_API_USER    : wazuh
  WAZUH_VERIFY_SSL  : false
  ZABBIX_API_URL    : http://192.168.10.4/zabbix/api_jsonrpc.php
  ZABBIX_ENABLED    : true

========================================
 BƯỚC 2: Kiểm tra Wazuh API
========================================

[INFO] Testing Wazuh API: https://192.168.10.4:55000
[INFO] Wazuh Host: 192.168.10.4
[INFO] Wazuh Port: 55000
[INFO] Test 1: Network connectivity...
[✓] Host 192.168.10.4 is reachable
[INFO] Test 2: Port connectivity...
[✓] Port 55000 is open on 192.168.10.4
[INFO] Test 3: HTTPS/TLS connectivity...
[✓] Wazuh API responds (HTTP 401)
[INFO] Test 4: Authentication...
[✓] Wazuh authentication successful
[INFO] Received token: eyJhbGciOiJFUzUx...
[INFO] Test 5: Fetching agents list...
[✓] Wazuh API trả về danh sách agents: 5 agents

... (more output)

╔════════════════════════════════════════════════════════════╗
║              DIAGNOSTIC SUMMARY                            ║
╚════════════════════════════════════════════════════════════╝

1. WAZUH API
   Status: OK
   ✓ Wazuh API hoạt động bình thường
   → Mini-SOC CÓ THỂ kết nối với Wazuh

2. ZABBIX API
   Status: OK
   ✓ Zabbix API hoạt động bình thường

3. MINI-SOC BACKEND
   Status: RUNNING
   ✓ Backend đang chạy

4. DATABASE
   ✓ Có 150 wazuh events
   → Hệ thống ĐÃ thu thập được dữ liệu
   ✓ Có 5 agents

╔════════════════════════════════════════════════════════════╗
║              KẾT LUẬN                                      ║
╚════════════════════════════════════════════════════════════╝

✓ HỆ THỐNG HOẠT ĐỘNG BÌNH THƯỜNG

Wazuh API hoạt động và hệ thống đã thu thập 150 events.
Dashboard sẽ hiển thị dữ liệu.

[✓] Báo cáo đã lưu: api_diagnostic_20260615_143022.txt
```

---

## 🎯 CHECKLIST SAU KHI CHẠY SCRIPT

Dựa vào kết quả, xác định:

- [ ] **Wazuh API Status**: OK / FAILED / NOT_CONFIGURED
- [ ] **Wazuh Authentication**: Success / Failed
- [ ] **Wazuh Returns Agents**: Yes / No
- [ ] **Zabbix Status**: OK / FAILED / DISABLED
- [ ] **Backend Running**: Yes / No
- [ ] **Database Has Events**: Yes (count: ___) / No
- [ ] **Alerts File Exists**: Yes / No
- [ ] **Volume Mount Correct**: Yes / No

### Nếu tất cả ✅:
→ Hệ thống hoạt động bình thường, dashboard sẽ có dữ liệu

### Nếu có ❌:
→ Xem phần "GIẢI PHÁP" trong output của script
→ Hoặc tham khảo section "GIẢI PHÁP" ở trên

---

## 📞 HỖ TRỢ THÊM

Nếu vẫn không xác định được vấn đề:

1. **Lưu báo cáo**: Script tự động tạo file `api_diagnostic_*.txt`
2. **Xem logs chi tiết**:
   ```bash
   docker logs mini_soc_backend_prod --tail 100
   ```
3. **Kiểm tra Wazuh logs**:
   ```bash
   tail -f /var/ossec/logs/ossec.log
   ```

---

## ✅ KẾT LUẬN

Script chẩn đoán này sẽ **XÁC ĐỊNH CHÍNH XÁC**:

- ✅ Wazuh API có hoạt động không
- ✅ Zabbix API có hoạt động không  
- ✅ Vấn đề từ đâu: Wazuh, Zabbix, hay Mini-SOC
- ✅ Credentials có đúng không
- ✅ Network/firewall có vấn đề không
- ✅ Data có được thu thập không

**Chạy ngay**:
```bash
sudo bash diagnose_api_connectivity.sh
```
