# 🚀 Hướng dẫn Triển khai Mini-SOC trên Server có Wazuh

> Deploy hệ thống Mini-SOC trên cùng server với Wazuh, truy cập qua IP address + port

## 📋 Yêu cầu Hệ thống

### Hardware Tối thiểu
- **CPU**: 4+ cores
- **RAM**: 8GB+ (16GB khuyến nghị)
- **Storage**: 50GB+ SSD
- **OS**: Ubuntu 20.04 LTS, CentOS 8, hoặc tương tự

### Phần mềm Yêu cầu
- Docker: 20.10+
- Docker Compose: 2.0+
- Git
- Server Wazuh: Đã cài đặt và chạy

### Port Không Xung đột
```
Wazuh:
- 1514/udp  : Wazuh agent events
- 1515/tcp  : Wazuh agent registration
- 514/udp   : Syslog
- 55000/tcp : Wazuh API

Mini-SOC (được chỉ định):
- 8080:tcp  : Nginx frontend
- 8000:tcp  : Backend API (internal)
- 5432:tcp  : PostgreSQL (internal, localhost chỉ)
- 6379:tcp  : Redis (internal, localhost chỉ)
```

## 🔧 Bước 1: Chuẩn bị Môi trường

### 1.1 Cập nhật Hệ thống
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget vim
```

### 1.2 Cài đặt Docker & Docker Compose
```bash
# Cài Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Cài Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
sudo ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose

# Kiểm tra
docker --version
docker-compose --version
```

### 1.3 Clone Repository
```bash
# Chọn thư mục triển khai (ví dụ: /opt)
cd /opt
sudo git clone <your-repo-url> mini-soc
sudo chown -R $USER:$USER mini-soc
cd mini-soc
```

## ⚙️ Bước 2: Cấu hình Port cho Mini-SOC

### 2.1 Sửa docker-compose.production.yml

**Mục đích**: Thay đổi port Nginx để không xung đột với Wazuh

```bash
nano docker-compose.production.yml
```

**Tìm và thay thế phần Nginx**:

```yaml
# Trước (dòng ~70)
  nginx:
    ...
    ports:
      - "80:80"        # ❌ Wazuh đã dùng port 80
      - "443:443"

# Sau (thay port 80 thành 8080)
  nginx:
    ...
    ports:
      - "8080:80"      # ✅ Nginx port 8080 → container port 80
      - "443:443"      # (SSL tùy chọn)
```

**Lưu**: Ctrl+X → Y → Enter

### 2.2 Cấu hình IP Binding (nếu cần)

Nếu muốn bind tất cả IP trên server (0.0.0.0):

```yaml
ports:
  - "0.0.0.0:8080:80"
  - "0.0.0.0:443:443"
```

Nếu muốn bind IP cụ thể (ví dụ: 192.168.1.100):

```yaml
ports:
  - "192.168.1.100:8080:80"
  - "192.168.1.100:443:443"
```

## 🗂️ Bước 3: Cấu hình Environment

### 3.1 Tạo File .env.production

```bash
cp .env.example .env.production
nano .env.production
```

### 3.2 Cấu hình Kết nối Wazuh

```env
# ========================================
# ENVIRONMENT CONFIGURATION
# ========================================
ENV=production
DEBUG=false

# ========================================
# DATABASE
# ========================================
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<STRONG_PASSWORD_HERE>  # Thay bằng mật khẩu mạnh
POSTGRES_DB=mini_soc_prod
POSTGRES_SERVER=db

# ========================================
# REDIS
# ========================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<REDIS_PASSWORD>  # Thay bằng mật khẩu mạnh
REDIS_DB=0

# ========================================
# WAZUH INTEGRATION
# ========================================
# Đường dẫn file alerts từ Wazuh
WAZUH_ALERTS_FILE=/var/ossec/logs/alerts/alerts.json
WAZUH_ALERTS_HOST_PATH=/var/ossec/logs/alerts  # Path trên host

# Wazuh API
WAZUH_API_URL=http://<WAZUH_SERVER_IP>:55000  # Ví dụ: http://192.168.1.100:55000
WAZUH_API_USER=wazuh
WAZUH_API_PASSWORD=<WAZUH_API_PASSWORD>       # Thay bằng mật khẩu Wazuh API

# ========================================
# APPLICATION
# ========================================
# Frontend URLs (sửa IP/port nếu cần)
VITE_API_URL=http://<SERVER_IP>:8080/api/v1
VITE_WS_URL=ws://<SERVER_IP>:8080/ws

# Thay <SERVER_IP> bằng:
# - IP thực tế của server nếu truy cập từ xa
# - localhost nếu chỉ truy cập local
# - Ví dụ: http://192.168.1.100:8080/api/v1

# ========================================
# SECURITY
# ========================================
SECRET_KEY=<GENERATE_SECRET>  # Chạy: python -c "import secrets; print(secrets.token_hex(32))"
CORS_ORIGINS=http://<SERVER_IP>:8080,http://localhost:8080
CORS_ALLOW_CREDENTIALS=true

# ========================================
# LOGGING & MONITORING
# ========================================
LOG_LEVEL=INFO
SENTRY_DSN=  # (Tùy chọn) Nếu dùng Sentry
```

### 3.3 Tạo SECRET_KEY

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
# Output: abcdef123456789...
# Copy vào ENVIRONMENT variable SECRET_KEY
```

## 🔌 Bước 4: Mount Alerts File từ Wazuh

### 4.1 Tìm Đường dẫn Wazuh Alerts

```bash
# SSH vào Wazuh server, hoặc chạy trực tiếp
sudo find / -name "alerts.json" 2>/dev/null | head -5
# Thường là: /var/ossec/logs/alerts/alerts.json
```

### 4.2 Cấu hình Mount Point

**Nếu Wazuh chạy trên cùng host:**

```bash
# Kiểm tra quyền
ls -la /var/ossec/logs/alerts/

# Cấp quyền (nếu cần)
sudo chmod 755 /var/ossec/logs/alerts/
sudo chmod 644 /var/ossec/logs/alerts/alerts.json
```

**Cập nhật .env.production:**

```env
WAZUH_ALERTS_HOST_PATH=/var/ossec/logs/alerts
```

**Nếu Wazuh chạy trên server khác:**

```bash
# Option 1: NFS Mount
# Cấu hình NFS trên Wazuh server để share /var/ossec/logs/alerts

# Option 2: API Integration
# Sử dụng Wazuh API để lấy alerts (thay vì file mount)
```

## 🚀 Bước 5: Deploy & Khởi động

### 5.1 Kiểm tra cấu hình

```bash
cd /opt/mini-soc

# Kiểm tra docker-compose.production.yml
docker-compose -f docker-compose.production.yml config | grep -A 5 "ports"

# Kiểm tra biến environment
cat .env.production | grep -E "WAZUH|VITE|SECRET"
```

### 5.2 Xây dựng Images

```bash
# Build frontend & backend (thường mất 5-10 phút)
docker-compose -f docker-compose.production.yml build --no-cache

# Hoặc chỉ build backend (nếu frontend không thay đổi)
docker-compose -f docker-compose.production.yml build --no-cache backend
```

### 5.3 Khởi động Services

```bash
# Khởi động tất cả services
docker-compose -f docker-compose.production.yml up -d

# Kiểm tra trạng thái
docker-compose -f docker-compose.production.yml ps

# Output mong đợi:
# NAME                          COMMAND                  SERVICE      STATUS
# mini_soc_nginx_prod           "nginx -g daemon off"    nginx        Up (healthy)
# mini_soc_frontend_prod        "npm run preview"        frontend     Up
# mini_soc_backend_prod         "python -m uvicorn..."   backend      Up (healthy)
# mini_soc_redis_prod           "redis-server..."        redis        Up (healthy)
# mini_soc_db_prod              "postgres"               db           Up (healthy)
```

### 5.4 Xem Log

```bash
# Xem log tất cả services
docker-compose -f docker-compose.production.yml logs -f

# Xem log riêng backend
docker-compose -f docker-compose.production.yml logs -f backend

# Xem log riêng nginx
docker-compose -f docker-compose.production.yml logs -f nginx

# Chỉ xem 50 dòng gần nhất
docker-compose -f docker-compose.production.yml logs --tail=50 backend
```

## 🌐 Bước 6: Truy cập Ứng dụng

### 6.1 URL Truy cập

```
Frontend (Web UI):
http://<SERVER_IP>:8080

API Docs:
http://<SERVER_IP>:8080/api/v1/docs

Health Check:
http://<SERVER_IP>:8080/api/v1/health/ready
```

**Thay `<SERVER_IP>` bằng:**
- IP thực tế của server: `192.168.1.100:8080`
- `localhost:8080` (nếu truy cập local)
- Hostname: `soc-server.local:8080`

### 6.2 Ví dụ Truy cập

```bash
# Từ máy khác trên LAN
curl http://192.168.1.100:8080

# Từ chính server (local)
curl http://localhost:8080

# Kiểm tra API
curl http://192.168.1.100:8080/api/v1/health/ready
```

### 6.3 Đăng nhập

1. Mở browser: `http://<SERVER_IP>:8080`
2. Tạo admin user:

```bash
docker-compose -f docker-compose.production.yml exec backend \
    python app/scripts/create_admin_user.py
```

3. Nhập thông tin:
   - Username: `admin`
   - Password: (mật khẩu mạnh)
   - Email: `admin@company.com`

4. Đăng nhập với credentials đã tạo

## ✅ Bước 7: Kết nối với Wazuh

### 7.1 Cấu hình Wazuh Data Provider

**File**: `backend/app/services/wazuh_data_provider.py`

```python
WAZUH_API_URL = os.getenv("WAZUH_API_URL")
WAZUH_API_USER = os.getenv("WAZUH_API_USER")
WAZUH_API_PASSWORD = os.getenv("WAZUH_API_PASSWORD")
```

### 7.2 Test Kết nối Wazuh

```bash
# SSH vào backend container
docker-compose -f docker-compose.production.yml exec backend bash

# Test API connection
python -c "
from app.integrations.wazuh_client import WazuhClient
client = WazuhClient()
agents = client.get_agents()
print(f'Agents: {len(agents)}')
"

# Thoát container
exit
```

### 7.3 Xem Alerts từ Wazuh

```bash
# Check log
docker-compose -f docker-compose.production.yml logs backend | grep -i "wazuh\|alert"

# Hoặc từ API
curl http://localhost:8080/api/v1/alerts | python -m json.tool
```

## 📊 Bước 8: Kiểm tra & Giám sát

### 8.1 Health Check

```bash
# Health check API
curl http://192.168.1.100:8080/api/v1/health/ready

# Response mong đợi:
# {"status":"ready","timestamp":"2024-01-15T10:30:00Z","version":"1.0.0"}
```

### 8.2 Kiểm tra Services

```bash
# Kiểm tra tất cả containers
docker ps | grep mini_soc

# Kiểm tra resource usage
docker stats

# Check specific container
docker inspect mini_soc_backend_prod | grep -A 5 '"State"'
```

### 8.3 Giám sát Logs

```bash
# Cài tail command (nếu cần)
sudo apt install -y tail

# Monitor real-time
docker-compose -f docker-compose.production.yml logs -f --tail=20

# Search errors
docker-compose -f docker-compose.production.yml logs | grep -i error
```

## 🔄 Bước 9: Cập nhật & Bảo trì

### 9.1 Cập nhật Code

```bash
cd /opt/mini-soc

# Pull mã mới
git pull origin main

# Rebuild & restart
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.production.yml build --no-cache
docker-compose -f docker-compose.production.yml up -d
```

### 9.2 Backup Database

```bash
# Backup PostgreSQL
docker-compose -f docker-compose.production.yml exec db \
    pg_dump -U postgres mini_soc_prod > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup Redis
docker-compose -f docker-compose.production.yml exec redis \
    redis-cli BGSAVE
```

### 9.3 Restart Services

```bash
# Restart tất cả
docker-compose -f docker-compose.production.yml restart

# Restart riêng backend
docker-compose -f docker-compose.production.yml restart backend

# Graceful restart
docker-compose -f docker-compose.production.yml down
docker-compose -f docker-compose.production.yml up -d
```

## 🛑 Bước 10: Troubleshooting

### Vấn đề: Port 8080 đã được sử dụng

```bash
# Tìm process sử dụng port 8080
sudo lsof -i :8080
# Hoặc: sudo netstat -tlnp | grep 8080

# Kill process (nếu cần)
sudo kill -9 <PID>

# Hoặc thay port trong docker-compose.production.yml
# ports:
#   - "8081:80"  # Đổi sang 8081
```

### Vấn đề: Container không khởi động

```bash
# Kiểm tra logs
docker-compose -f docker-compose.production.yml logs backend

# Kiểm tra config
docker-compose -f docker-compose.production.yml config

# Rebuild
docker-compose -f docker-compose.production.yml build --no-cache backend
```

### Vấn đề: Không kết nối được Wazuh API

```bash
# Kiểm tra Wazuh API
curl -k https://<WAZUH_IP>:55000/security/user/authenticate \
  -u wazuh:wazuh

# Kiểm tra firewall
sudo ufw allow 55000/tcp
sudo firewall-cmd --permanent --add-port=55000/tcp

# Test từ Mini-SOC container
docker-compose -f docker-compose.production.yml exec backend \
    curl http://wazuh-server:55000/security/user/authenticate \
    -u wazuh:password
```

### Vấn đề: Không thấy Wazuh Alerts

```bash
# Kiểm tra alerts file
ls -la /var/ossec/logs/alerts/alerts.json

# Kiểm tra quyền
stat /var/ossec/logs/alerts/alerts.json

# Check Docker mount
docker-compose -f docker-compose.production.yml exec backend \
    ls -la /var/ossec/logs/alerts/

# Xem logs backend
docker-compose -f docker-compose.production.yml logs backend | grep -i alert
```

## 📝 Checklist Triển khai

- [ ] Docker & Docker Compose cài đặt
- [ ] Repository cloned
- [ ] Port 8080 không xung đột
- [ ] .env.production cấu hình đầy đủ
- [ ] Wazuh alerts file được mount
- [ ] Services khởi động thành công
- [ ] Frontend truy cập được
- [ ] API health check OK
- [ ] Admin user tạo thành công
- [ ] Kết nối Wazuh API OK
- [ ] Alerts được lấy từ Wazuh
- [ ] Database backup có sẵn

## 🆘 Hỗ trợ & Tài liệu

**Logs quan trọng:**
- Backend: `docker logs mini_soc_backend_prod`
- Nginx: `docker logs mini_soc_nginx_prod`
- Database: `docker logs mini_soc_db_prod`

**Kiểm tra cấu hình:**
```bash
cat .env.production
docker-compose -f docker-compose.production.yml config
```

**Tài liệu:**
- [Docker Documentation](https://docs.docker.com)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Wazuh API Reference](https://documentation.wazuh.com/current/user-manual/api/reference.html)
- [PostgreSQL Docs](https://www.postgresql.org/docs)

---

**Lần cập nhật**: May 2026
**Version**: 1.0
