# 🛡️ Mini-SOC Portal

**Enterprise-grade Security Operations Center platform with Wazuh integration**

[![Production Ready](https://img.shields.io/badge/production-ready-brightgreen)](.)
[![Docker](https://img.shields.io/badge/docker-20.10+-blue)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![React](https://img.shields.io/badge/react-18-blue)](https://reactjs.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🎯 Overview

Mini-SOC Portal is a production-ready Security Operations Center platform that provides real-time threat monitoring, incident management, and security analytics. Built with modern technologies and best practices for enterprise deployments.

### Key Features

- **Real-time Monitoring** - Live alert collection from Wazuh with WebSocket updates
- **Threat Intelligence** - GeoIP enrichment, risk scoring, MITRE ATT&CK mapping
- **Incident Management** - Automated correlation, workflow tracking, team collaboration
- **Executive Dashboard** - Real-time metrics, charts, severity distribution
- **Advanced Analytics** - Attack patterns, top IPs, server status, audit logs
- **Production-Grade** - Connection pooling, rate limiting, health checks, graceful shutdown

---

## 🚀 Quick Start (ONE COMMAND!)

Deploy entire system in 10-15 minutes:

```bash
sudo bash deploy_on_wazuh.sh
```

That's it! The script handles everything:
- ✅ Dependency checks
- ✅ Configuration generation
- ✅ Docker build & deployment
- ✅ Database migrations
- ✅ Admin user creation
- ✅ Validation (8 automated tests)

**See [ONE_COMMAND_DEPLOY.md](ONE_COMMAND_DEPLOY.md) for detailed guide.**

---

## 📋 System Requirements

### Hardware
- **CPU:** 2 cores minimum (4 cores recommended)
- **RAM:** 4GB minimum (8GB recommended)
- **Disk:** 20GB free space
- **Network:** Internet access for installation

### Software
- **OS:** Ubuntu 20.04/22.04 or Debian 10/11
- **Docker:** 20.10+
- **Docker Compose:** 1.29+
- **Wazuh:** 4.x (must be installed)
- **Git:** 2.x

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend (React)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │Dashboard │  │  Alerts  │  │Incidents │  │Analytics │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/WS
┌────────────────────────┴────────────────────────────────────┐
│                    Nginx Reverse Proxy                       │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────────┐
│                   Backend API (FastAPI)                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │
│  │  Auth   │  │  CRUD   │  │WebSocket│  │ Health  │       │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘       │
└───┬──────────┬────────────┬──────────────┬─────────────────┘
    │          │            │              │
┌───┴───┐  ┌───┴───┐  ┌─────┴─────┐  ┌───┴────────┐
│ Redis │  │ PostgreSQL │ Collector │  │  Wazuh API │
│PubSub │  │  Database  │  Service  │  │ (External) │
└───────┘  └───────────┘  └─────┬─────┘  └────────────┘
                                 │
                         ┌───────┴────────┐
                         │ Wazuh Alerts   │
                         │ alerts.json    │
                         └────────────────┘
```

### Components

- **Frontend:** React 18 + TypeScript + Tailwind CSS
- **Backend:** FastAPI + SQLAlchemy + Pydantic
- **Database:** PostgreSQL 16 with async driver
- **Cache:** Redis 7 for pub/sub and caching
- **Proxy:** Nginx for reverse proxy and SSL termination
- **Collector:** Async file tailer for Wazuh alerts

---

## 🎨 Features

### Security Operations
- ✅ Real-time alert collection (Wazuh → Collector → DB → UI)
- ✅ Threat intelligence (GeoIP, risk scoring, country detection)
- ✅ Correlation engine (IP-based, agent-based, pattern matching)
- ✅ Incident workflow (create, assign, track, resolve)
- ✅ MITRE ATT&CK mapping (tactics & techniques)
- ✅ Alert suppression (prevent alert fatigue)

### User Interface
- ✅ Executive dashboard (metrics, charts, trends)
- ✅ Analyst dashboard (active threats, assignments)
- ✅ Alerts management (filter, search, pagination)
- ✅ Incident tracking (status, severity, timeline)
- ✅ Agent monitoring (status, risk score, alerts count)
- ✅ Audit logging (all user actions tracked)

### Technical Excellence
- ✅ JWT authentication with refresh tokens
- ✅ RBAC (5 roles: Super Admin, SOC Analyst, IT Admin, Manager, Auditor)
- ✅ CSRF protection with secure cookies
- ✅ Rate limiting (login, API, WebSocket)
- ✅ Connection pooling (20-40 connections)
- ✅ Health checks (database, Redis, collector)
- ✅ Structured logging with correlation IDs
- ✅ Metrics endpoints (Prometheus-compatible)

---

## 📊 Technology Stack

### Backend
- **Framework:** FastAPI 0.104+
- **Database:** PostgreSQL 16 + asyncpg
- **ORM:** SQLAlchemy 2.0 (async)
- **Validation:** Pydantic 2.0
- **Migration:** Alembic
- **Cache:** Redis 7 + aioredis
- **Auth:** JWT + Argon2 password hashing
- **Logging:** structlog
- **Testing:** pytest + pytest-asyncio

### Frontend
- **Framework:** React 18 + TypeScript
- **State:** Zustand
- **UI:** Tailwind CSS + HeadlessUI
- **Charts:** Recharts
- **HTTP:** Axios
- **Icons:** Lucide React
- **Build:** Vite 5

### Infrastructure
- **Containerization:** Docker + Docker Compose
- **Reverse Proxy:** Nginx
- **Process Manager:** dumb-init
- **Orchestration:** Docker Compose Production

---

## 📁 Project Structure

```
Mini-SOC/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   ├── core/            # Config, database, security
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   ├── collector/       # Wazuh alert collector
│   │   ├── middleware/      # Custom middleware
│   │   ├── integrations/    # Wazuh, OpenSearch clients
│   │   └── websocket/       # WebSocket manager
│   ├── alembic/             # Database migrations
│   ├── requirements.txt
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── features/        # Feature modules
│   │   ├── shared/          # Shared components
│   │   ├── layouts/         # Page layouts
│   │   └── hooks/           # Custom hooks
│   ├── package.json
│   └── vite.config.ts
├── docker/
│   ├── backend.Dockerfile
│   ├── frontend.Dockerfile
│   └── nginx.Dockerfile
├── docker-compose.production.yml
├── deploy_on_wazuh.sh      # ONE-COMMAND DEPLOY
├── nginx.conf
└── README.md
```

---

## 🔧 Configuration

### Environment Variables (.env.production)

Auto-generated by deploy script, key variables:

```bash
# Security
SECRET_KEY="auto-generated-64-char-hex"
POSTGRES_PASSWORD="auto-generated-base64"
REDIS_PASSWORD="auto-generated-base64"

# Database
POSTGRES_DB="mini_soc_prod"
DB_POOL_SIZE="20"

# Wazuh
WAZUH_API_URL="http://server-ip:55000"
WAZUH_ALERTS_FILE="/var/ossec/logs/alerts/alerts.json"

# Frontend
VITE_API_URL="http://server-ip:2709/api/v1"
VITE_WS_URL="ws://server-ip:2709/ws"

# CORS
BACKEND_CORS_ORIGINS="http://server-ip:2709,..."
```

**See [.env.example](backend/.env.example) for all variables.**

---

## 🧪 Testing

### Automated Tests

```bash
# Backend unit tests
cd backend
pytest

# Frontend tests
cd frontend
npm test

# Collector validation
python3 test_wazuh_collector.py

# End-to-end validation
bash validate_data_flow.sh
```

### Manual Testing

```bash
# 1. Inject test data
bash inject_test_data.sh

# 2. Open browser
xdg-open http://localhost:2709

# 3. Login with admin credentials
# 4. Verify dashboard shows 8 test alerts
# 5. Check all pages load correctly
```

---

## 📚 Documentation

### Deployment
- **[ONE_COMMAND_DEPLOY.md](ONE_COMMAND_DEPLOY.md)** - One-command deployment guide
- **[DEPLOY_QUICKSTART.md](DEPLOY_QUICKSTART.md)** - Quick reference
- **[FINAL_DEPLOYMENT_CHECKLIST.md](FINAL_DEPLOYMENT_CHECKLIST.md)** - Complete checklist

### Technical
- **[DATA_FLOW_VALIDATION.md](DATA_FLOW_VALIDATION.md)** - Data flow architecture
- **[COLLECTOR_FIXES.md](COLLECTOR_FIXES.md)** - Collector implementation
- **[BUGFIX_SUMMARY.md](BUGFIX_SUMMARY.md)** - All bugs fixed (9 total)

### Operations
- **validate_deployment.sh** - Post-deploy health checks
- **debug_deployment.sh** - Troubleshooting tool
- **validate_data_flow.sh** - End-to-end data validation
- **inject_test_data.sh** - Test data generator

---

## 🚨 Troubleshooting

### Common Issues

#### No Data in Dashboard
```bash
# Check Wazuh alerts file
tail -f /var/ossec/logs/alerts/alerts.json

# Inject test data
bash inject_test_data.sh

# Check collector logs
docker-compose -f docker-compose.production.yml logs backend | grep collector
```

#### 401/403 Auth Errors
```bash
# Run diagnostic
bash diagnose_auth_issues.sh

# Auto-fix
bash fix_auth_websocket.sh
```

#### WebSocket Connection Failed
```bash
# Check VITE_WS_URL
grep VITE_WS_URL .env.production

# Should be: ws://server-ip:port/ws (NOT /ws/ws)

# Fix if wrong
bash fix_auth_websocket.sh
```

#### Containers Not Starting
```bash
# Check logs
docker-compose -f docker-compose.production.yml logs

# Restart
docker-compose -f docker-compose.production.yml restart

# Full reset
docker-compose -f docker-compose.production.yml down -v
sudo bash deploy_on_wazuh.sh
```

**See [DEBUG_GUIDE.md](debug_deployment.sh) for more solutions.**

---

## 🔒 Security

### Authentication & Authorization
- JWT tokens with 15min expiry
- Refresh tokens with 7-day expiry
- Argon2 password hashing
- RBAC with 5 predefined roles
- CSRF protection
- Secure HTTP-only cookies

### Network Security
- Rate limiting (10 login attempts/min)
- CORS configured
- Security headers (CSP, HSTS, X-Frame-Options)
- SQL injection protection (parameterized queries)
- XSS protection (output encoding)

### Data Security
- Passwords never logged
- Secrets in environment variables
- Database credentials auto-generated
- TLS/SSL ready (add certificates)

### Audit Trail
- All user actions logged
- IP address tracking
- Correlation IDs for request tracing
- Structured logging format

---

## 📈 Performance

### Benchmarks
- **API Response Time:** 50-200ms (average)
- **Database Queries:** <50ms (with indexes)
- **WebSocket Latency:** <100ms
- **Alert Processing:** 100-1000 events/min
- **Concurrent Users:** 50+ (tested)

### Optimization
- Connection pooling (20-40 connections)
- Redis caching (GeoIP, sessions)
- Database indexes on all queries
- Async I/O throughout
- Query result pagination
- Frontend code splitting

### Resource Usage
```
Backend:  300-500MB RAM, 5-15% CPU
Frontend: 50-100MB RAM, 0-1% CPU
Database: 150-300MB RAM, 2-5% CPU
Redis:    50-100MB RAM, 0-2% CPU
Nginx:    20-50MB RAM, 0-1% CPU
```

---

## 🤝 Contributing

### Development Setup
```bash
# Clone repository
git clone https://github.com/your-org/Mini-SOC.git
cd Mini-SOC

# Start dev environment
docker-compose up -d

# Backend dev server
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend dev server
cd frontend
npm install
npm run dev
```

### Code Style
- **Backend:** black + isort + ruff
- **Frontend:** ESLint + Prettier
- **Commits:** Conventional Commits

---

## 📝 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.

---

## 👥 Team

- **Development:** Security Operations Team
- **Maintainer:** [Your Name]
- **Support:** support@example.com

---

## 🙏 Acknowledgments

- [Wazuh](https://wazuh.com/) - Open source SIEM platform
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python framework
- [React](https://reactjs.org/) - UI library
- [PostgreSQL](https://www.postgresql.org/) - Database
- [Redis](https://redis.io/) - Caching & pub/sub

---

## 📞 Support

- **Documentation:** [docs/](docs/)
- **Issues:** [GitHub Issues](https://github.com/your-org/Mini-SOC/issues)
- **Email:** support@example.com

---

## 🎉 Getting Started

```bash
# ONE COMMAND TO DEPLOY:
sudo bash deploy_on_wazuh.sh

# ACCESS SYSTEM:
http://your-server-ip:2709

# DEFAULT CREDENTIALS:
# Will be created during deployment
```

**Deploy in 10-15 minutes. No manual configuration needed!** 🚀

---

**Last Updated:** 2026-06-08  
**Version:** 2.0.0  
**Status:** ✅ Production Ready
