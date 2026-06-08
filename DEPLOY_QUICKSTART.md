# 🚀 Deploy Quick Start Guide

## Prerequisites

- [x] Ubuntu/Debian server với Wazuh đã cài đặt
- [x] Docker + Docker Compose installed
- [x] Root/sudo access
- [x] Port 2709 available (hoặc custom port)

---

## One-Command Deploy

```bash
sudo bash deploy_on_wazuh.sh
```

Script sẽ hỏi:
1. **Deployment path** (default: `/opt/mini-soc`)
2. **Nginx port** (default: `2709`)
3. **Server IP** (auto-detect)
4. **Wazuh API URL** (default: `http://<server-ip>:55000`)
5. **Wazuh credentials**
6. **Admin username/email/password**

---

## After Deployment

### 1. Verify Health
```bash
bash validate_deployment.sh
```

### 2. Access System
```
Web UI:    http://<server-ip>:2709
API Docs:  http://<server-ip>:2709/api/v1/docs (if DEBUG=true)
Health:    http://<server-ip>:2709/api/v1/health/ready
```

### 3. View Logs
```bash
cd /opt/mini-soc
docker-compose -f docker-compose.production.yml logs -f backend
```

---

## Common Commands

### Check Status
```bash
docker-compose -f docker-compose.production.yml ps
```

### Restart Service
```bash
docker-compose -f docker-compose.production.yml restart backend
```

### Stop All
```bash
docker-compose -f docker-compose.production.yml down
```

### Start All
```bash
docker-compose -f docker-compose.production.yml up -d
```

### Rebuild Backend (After Code Changes)
```bash
bash hotfix_rebuild.sh
```

---

## Troubleshooting

### If deployment fails
```bash
bash debug_deployment.sh
```

### View specific logs
```bash
# Backend
docker-compose -f docker-compose.production.yml logs --tail 100 backend

# Database
docker-compose -f docker-compose.production.yml logs --tail 100 db

# All services
docker-compose -f docker-compose.production.yml logs --tail 50
```

### Reset database (⚠️ DESTRUCTIVE)
```bash
docker-compose -f docker-compose.production.yml down -v
sudo bash deploy_on_wazuh.sh  # Re-deploy
```

---

## Important Files

| File | Purpose |
|------|---------|
| `.env.production` | Configuration (passwords, secrets) |
| `docker-compose.production.yml` | Service definitions |
| `deploy_on_wazuh.sh` | Main deploy script |
| `validate_deployment.sh` | Health checks |
| `debug_deployment.sh` | Troubleshooting |
| `hotfix_rebuild.sh` | Quick backend rebuild |

---

## Security Checklist

- [ ] Change admin password after first login
- [ ] Backup `.env.production` securely
- [ ] Enable firewall: `sudo ufw allow 2709/tcp`
- [ ] Rotate secrets monthly
- [ ] Enable HTTPS in production
- [ ] Regular backups: `docker-compose exec db pg_dump`

---

## Next Steps

1. Login to web UI with admin credentials
2. Configure Wazuh agents to send alerts
3. Verify alerts are being collected
4. Set up monitoring dashboards
5. Configure alert rules
6. Add SOC team members

---

**Need Help?** Check `BUGFIX_SUMMARY.md` for detailed troubleshooting.
