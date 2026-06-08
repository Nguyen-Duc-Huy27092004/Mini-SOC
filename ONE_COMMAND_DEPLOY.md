# 🚀 ONE-COMMAND DEPLOY - Mini-SOC

## ✨ Overview

Deploy toàn bộ hệ thống Mini-SOC **CHỈ VỚI 1 LỆNH DUY NHẤT**:

```bash
sudo bash deploy_on_wazuh.sh
```

**Thời gian:** 10-15 phút  
**Yêu cầu:** Server có Wazuh + Docker + Internet

---

## 🎯 What This Script Does

### Automatic Steps (No Manual Intervention Needed)

1. ✅ **Pre-flight Checks**
   - Verify Docker installed
   - Verify Docker Compose installed
   - Verify Git installed
   - Check Wazuh is running
   - Verify port availability

2. ✅ **Configuration**
   - Generate secure passwords (openssl rand)
   - Generate JWT secret key
   - Detect server IP automatically
   - Create .env.production with all settings
   - Configure CORS, cookies, CSRF

3. ✅ **Repository**
   - Clone or update from Git
   - Backup existing configs

4. ✅ **Docker Setup**
   - Clean old containers
   - Build backend image
   - Build frontend image
   - Verify builds successful

5. ✅ **Database**
   - Start PostgreSQL
   - Wait for readiness (120s timeout)
   - Run ALL migrations (001 → 005)
   - Verify migration success

6. ✅ **Services**
   - Start Redis
   - Start backend (with health checks)
   - Start frontend
   - Start Nginx
   - Wait for all services ready

7. ✅ **Admin User**
   - Prompt for email & password
   - Create admin user in database
   - Assign Super Admin role

8. ✅ **Validation (8 Tests)**
   - Container status check
   - Database connectivity
   - Migration verification
   - Redis connectivity
   - Backend API health
   - Frontend accessibility
   - Collector service
   - Error scanning

9. ✅ **Output**
   - Display access URLs
   - Save credentials to file
   - Show useful commands
   - Security reminders

---

## 📋 Prerequisites

### System Requirements
```bash
# Operating System
Ubuntu 20.04/22.04 or Debian 10/11

# Resources
RAM: 4GB minimum (8GB recommended)
CPU: 2 cores minimum (4 cores recommended)
Disk: 20GB free space

# Software
Docker: 20.10+
Docker Compose: 1.29+
Git: 2.x
Wazuh: 4.x (already installed)
```

### Quick Install (If Not Installed)
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Git
sudo apt update && sudo apt install -y git

# Verify
docker --version
docker-compose --version
git --version
```

---

## 🚀 Deployment Steps

### Step 1: Download Script
```bash
# Option A: Clone repository
git clone https://github.com/your-org/Mini-SOC.git
cd Mini-SOC

# Option B: Direct download
wget https://raw.githubusercontent.com/your-org/Mini-SOC/main/deploy_on_wazuh.sh
```

### Step 2: Run Deployment
```bash
sudo bash deploy_on_wazuh.sh
```

### Step 3: Answer Prompts
```
Enter deployment path (default: /opt/mini-soc): [ENTER]
Enter Nginx port (default: 2709): [ENTER]
Enter server IP: [AUTO-DETECTED - ENTER]
Enter Wazuh API URL: [AUTO-DETECTED - ENTER]
Enter Wazuh API username: wazuh
Enter Wazuh API password: [YOUR-WAZUH-PASSWORD]
Enter admin username: admin
Enter admin email: admin@example.com
Enter admin password: [STRONG-PASSWORD-8+CHARS]
```

### Step 4: Wait for Completion
```
Building Docker images (5-10 minutes)...
Starting services...
Running migrations...
Validating deployment...
✅ DEPLOYMENT VALIDATION PASSED
```

### Step 5: Access System
```bash
# Open browser
http://<your-server-ip>:2709

# Login with admin credentials
```

---

## ✅ Success Indicators

### During Deployment
```
[✓] Docker found: Docker version 24.0.7
[✓] Docker Compose found: v2.20.0
[✓] Git found: git version 2.34.1
[✓] Wazuh appears to be running
[✓] Configuration generated
[✓] Repository cloned
[✓] Backend image built
[✓] Frontend image built
[✓] PostgreSQL is ready
[✓] Redis is ready
[✓] Database migrations completed SUCCESSFULLY
[✓] Backend is healthy
[✓] Nginx is serving requests
[✓] Admin user created successfully
[1/8] ✓ All containers are running (5/5)
[2/8] ✓ PostgreSQL is accessible
[3/8] ✓ Latest migration applied: 005_fill_missing_columns
[4/8] ✓ Redis is accessible
[5/8] ✓ Backend health check passed
[6/8] ✓ Frontend is accessible
[7/8] ✓ Collector service started
[8/8] ✓ No critical errors in logs

✅ DEPLOYMENT VALIDATION PASSED
```

### After Deployment
```bash
# Check containers
docker ps

# Expected output:
CONTAINER ID   IMAGE                      STATUS
abc123         mini_soc_nginx_prod        Up 2 minutes (healthy)
def456         mini_soc_backend_prod      Up 2 minutes (healthy)
ghi789         mini_soc_frontend_prod     Up 2 minutes
jkl012         postgres:16-alpine         Up 3 minutes (healthy)
mno345         redis:7-alpine             Up 3 minutes (healthy)

# Test health endpoint
curl http://localhost:2709/api/v1/health/ready

# Expected: {"status":"ok","checks":{"database":"ok","redis":"ok"}}

# Check deployment info
cat /opt/mini-soc/DEPLOYMENT_INFO.txt
```

---

## 🔧 What Gets Configured

### Automatic Configuration

#### .env.production
```bash
# Security (Auto-generated)
SECRET_KEY="random-64-char-hex"
POSTGRES_PASSWORD="random-base64-32"
REDIS_PASSWORD="random-base64-32"

# CORS (Auto-configured)
BACKEND_CORS_ORIGINS="http://server-ip:2709,..."

# Cookies (Production-safe)
COOKIE_SECURE="false"  # HTTP mode
CSRF_VALIDATE_ORIGIN="false"  # Same-origin

# WebSocket (Correct path)
VITE_WS_URL="ws://server-ip:2709/ws"  # NOT /ws/ws!

# Wazuh Integration
WAZUH_API_URL="http://server-ip:55000"
WAZUH_ALERTS_FILE="/var/ossec/logs/alerts/alerts.json"

# Database
POSTGRES_DB="mini_soc_prod"
DB_POOL_SIZE="20"

# All 50+ variables configured correctly
```

#### Docker Volumes
```yaml
volumes:
  - postgres_data_prod:/var/lib/postgresql/data
  - redis_data_prod:/data
  - /var/ossec/logs/alerts:/var/ossec/logs/alerts:ro
```

#### Network
```yaml
networks:
  soc_network:
    driver: bridge
```

---

## 🛡️ Safety Features

### Built-in Protection

1. **Pre-flight Validation**
   - All dependencies checked before starting
   - Port conflicts detected
   - Wazuh connectivity verified

2. **Error Handling**
   - Every step has error checking
   - Failed steps exit immediately
   - Helpful error messages with solutions

3. **Rollback Capability**
   ```bash
   # Backups created:
   docker-compose.production.yml.bak
   DEPLOYMENT_INFO.txt (with all passwords)
   
   # Rollback if needed:
   docker-compose -f docker-compose.production.yml down -v
   # Re-run script
   ```

4. **Password Security**
   - Passwords generated with openssl
   - Stored in chmod 600 file
   - Never logged to console (read -sp)

5. **Health Checks**
   - Database readiness: 120s timeout
   - Backend readiness: 120s timeout
   - Migration verification
   - API health check
   - Frontend accessibility

6. **Validation Tests**
   - 8 automated tests after deployment
   - Clear pass/fail indicators
   - Troubleshooting hints if failed

---

## 🚨 Common Issues & Auto-Fixes

### Issue 1: Port Already in Use
```
[✗] Port 2709 is already in use

Auto-fix: Script exits immediately
Solution: Stop service using port or choose different port
```

### Issue 2: Database Not Ready
```
[✗] Database failed to start after 120 seconds

Auto-fix: Script exits with error logs
Solution: Check docker logs, increase timeout, retry
```

### Issue 3: Migration Failed
```
[✗] Database migration failed!

Auto-fix: Script shows migration logs
Solution: Check alembic version, database schema, retry
```

### Issue 4: Backend Build Failed
```
[✗] Backend build failed!

Auto-fix: Build logs saved to /tmp/backend_build.log
Solution: Check requirements.txt, Dockerfile, retry
```

### Issue 5: WebSocket Path Wrong
```
⚠️ VITE_WS_URL has /ws/ws

Auto-fix: Script now generates correct ws://ip:port/ws
Solution: N/A - Already fixed in latest version
```

---

## 📊 Performance Expectations

### Deploy Time
- **Repository clone:** 30-60s (depends on internet)
- **Docker build (backend):** 3-5 minutes
- **Docker build (frontend):** 2-3 minutes
- **Database init:** 10-20s
- **Migrations:** 5-10s
- **Service startup:** 30-60s
- **Validation:** 10-20s

**Total:** 10-15 minutes

### Resource Usage After Deploy
```bash
docker stats

# Expected:
NAME                    CPU %     MEM USAGE / LIMIT
mini_soc_backend_prod   5-15%     300-500MB / 2GB
mini_soc_frontend_prod  0-1%      50-100MB / 512MB
mini_soc_db_prod        2-5%      150-300MB / 1GB
mini_soc_redis_prod     0-2%      50-100MB / 512MB
mini_soc_nginx_prod     0-1%      20-50MB / 256MB
```

---

## 🔍 Post-Deployment Checks

### Automated (Done by Script)
- [x] Containers running
- [x] Database accessible
- [x] Migrations applied
- [x] Redis working
- [x] API responding
- [x] Frontend serving
- [x] Collector started
- [x] No critical errors

### Manual (Recommended)
```bash
# 1. Login to web UI
xdg-open http://$(hostname -I | awk '{print $1}'):2709

# 2. Check dashboard loads
# Should see: Summary cards, charts, recent alerts

# 3. Verify Wazuh integration
# Alerts page should populate within 5 minutes

# 4. Test WebSocket realtime
# Browser console should show: "WebSocket connected"

# 5. Check logs for errors
docker-compose -f /opt/mini-soc/docker-compose.production.yml logs | grep -i error
```

---

## 📚 Files Created

### After Deployment
```
/opt/mini-soc/
├── .env.production                    # All configuration
├── .env.production.bak               # Backup
├── docker-compose.production.yml     # Services definition
├── docker-compose.production.yml.bak # Backup
├── DEPLOYMENT_INFO.txt               # Credentials (chmod 600)
├── backend/                          # Backend code
├── frontend/                         # Frontend code
├── data/
│   └── wazuh/                       # Wazuh alerts mount
└── db_backups/                       # Database backups location
```

### Important Files
- **DEPLOYMENT_INFO.txt** - Contains ALL passwords, keep secure!
- **.env.production** - Runtime configuration
- **docker-compose.production.yml** - Service definitions

---

## 🎓 What You Get

### Fully Configured System
- ✅ PostgreSQL database (schema + indexes)
- ✅ Redis cache (pub/sub configured)
- ✅ Backend API (50+ endpoints)
- ✅ Frontend UI (responsive, dark theme)
- ✅ Nginx reverse proxy
- ✅ Wazuh integration (file tailing + API)
- ✅ Admin user created
- ✅ SSL-ready (add certs to enable)

### Zero Manual Config Needed
- ✅ CORS configured
- ✅ Cookies configured
- ✅ CSRF configured
- ✅ WebSocket path correct
- ✅ Database migrations applied
- ✅ Collector auto-starts
- ✅ All ENV vars set

### Production-Ready Features
- ✅ Health checks enabled
- ✅ Connection pooling
- ✅ Rate limiting
- ✅ Security headers
- ✅ Structured logging
- ✅ Metrics endpoints
- ✅ Graceful shutdown

---

## 🆘 Getting Help

### If Deployment Fails

1. **Read error message** - Script shows detailed errors
2. **Check logs** - Located in /tmp/*.log files
3. **Review DEPLOYMENT_INFO.txt** - Has system state
4. **Re-run script** - Often fixes transient issues
5. **Manual cleanup**:
   ```bash
   cd /opt/mini-soc
   docker-compose -f docker-compose.production.yml down -v
   sudo bash deploy_on_wazuh.sh  # Try again
   ```

### If System Not Working

1. **Run validation**:
   ```bash
   cd /opt/mini-soc
   bash validate_deployment.sh  # If available
   ```

2. **Check all containers**:
   ```bash
   docker-compose -f docker-compose.production.yml ps
   ```

3. **Check logs**:
   ```bash
   docker-compose -f docker-compose.production.yml logs --tail 100 backend
   ```

4. **Restart services**:
   ```bash
   docker-compose -f docker-compose.production.yml restart
   ```

---

## ✅ Success Checklist

After running `sudo bash deploy_on_wazuh.sh`, verify:

- [ ] Script completed without errors
- [ ] Validation tests all passed (8/8)
- [ ] DEPLOYMENT_INFO.txt file created
- [ ] All 5 containers running
- [ ] Can access http://server-ip:2709
- [ ] Can login with admin credentials
- [ ] Dashboard loads and shows data
- [ ] No errors in browser console
- [ ] WebSocket shows "connected"

**If all checked:** 🎉 **DEPLOYMENT SUCCESSFUL!**

---

## 🚀 Summary

```bash
# ONE COMMAND TO DEPLOY EVERYTHING:
sudo bash deploy_on_wazuh.sh

# WHAT IT DOES:
✓ Checks prerequisites (Docker, Wazuh, Git)
✓ Generates secure credentials
✓ Clones repository
✓ Builds Docker images
✓ Runs database migrations
✓ Starts all services
✓ Creates admin user
✓ Validates deployment (8 tests)
✓ Saves credentials securely

# TIME: 10-15 minutes
# RESULT: Fully functional Mini-SOC
```

**NO manual configuration needed. Just run and go!** 🎉

---

**Last Updated:** 2026-06-08  
**Script Version:** 2.0.0  
**Status:** Production Ready ✅
