# Mini SOC Portal - Production Ready

> **🎯 Status:** 70% Production-Ready | Fully deployable with configuration

A comprehensive Security Operations Center (SOC) portal with real-time alert monitoring, incident tracking, and security analytics.

## 🚀 Quick Start

### Development (Local)
```bash
# 1. Clone repository
git clone <repo-url>
cd Mini-SOC

# 2. Create development environment
cp .env.development .env

# 3. Start services
docker-compose up -d

# 4. Access application
# Frontend: http://localhost
# Backend: http://localhost/api/v1
# Docs: http://localhost/docs
```

### Production (Deployment)
```bash
# 1. Prepare environment
cp .env.production .env
# Edit .env with production values

# 2. Obtain SSL certificates
certbot certonly --standalone -d yourdomain.com
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ./ssl/
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ./ssl/

# 3. Deploy
docker-compose -f docker-compose.production.yml up -d

# 4. Verify
curl https://yourdomain.com/api/v1/health
```

## 📋 What's Production-Ready

✅ **Completed**
- Security headers and HTTPS/SSL support
- Environment-based configuration (dev/prod separation)
- Graceful shutdown handling
- Health checks and monitoring
- Container resource limits
- Database connection pooling
- API rate limiting (Nginx level)
- Error handling and logging
- Secrets management (via environment variables)
- Multi-stage Docker builds

⚠️ **Needs Configuration**
- SSL certificates (Let's Encrypt)
- Environment variables in production
- Monitoring setup (Sentry, ELK, Prometheus)
- Database backups scheduling
- Log aggregation

❌ **Not Included**
- CI/CD pipeline (GitHub Actions)
- Kubernetes manifests
- Load testing results
- Complete test coverage

## 🏗️ Project Structure

```
Mini-SOC/
├── backend/                  # FastAPI Backend
│   ├── main.py              # Entry point
│   ├── requirements.txt      # Dependencies
│   └── app/
│       ├── api/             # API endpoints (v1)
│       ├── core/            # Configuration, DB, security
│       ├── models/          # Database models
│       ├── services/        # Business logic
│       └── schemas/         # Request/response schemas
├── frontend/                 # React + TypeScript
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom hooks
│   │   ├── services/        # API client
│   │   └── store/           # State management (Zustand)
│   ├── package.json         # Dependencies
│   └── vite.config.ts       # Build configuration
├── docker/                   # Docker configurations
│   ├── backend.Dockerfile   # Backend container
│   └── frontend.Dockerfile  # Frontend container
├── nginx.conf               # Nginx reverse proxy
├── docker-compose.yml       # Development setup
├── docker-compose.production.yml  # Production setup
├── .env.development         # Dev environment template
├── .env.production          # Prod environment template
├── DEPLOYMENT.md            # Deployment guide
└── PRODUCTION_READINESS.md  # Improvements made
```

## 🔧 Technology Stack

### Backend
- **FastAPI** 0.111.0 - Modern Python web framework
- **SQLAlchemy 2.0** - ORM with async support
- **PostgreSQL 16** - Primary database
- **Redis 7** - Caching & pub/sub
- **OpenSearch 2.11** - SIEM data storage
- **Uvicorn** - ASGI server with multiple workers

### Frontend
- **React 18.3** - UI framework
- **TypeScript 5.2** - Type safety
- **Vite 5.2** - Fast build tool
- **Tailwind CSS** - Styling
- **Zustand** - State management
- **Axios** - HTTP client

### Infrastructure
- **Docker** - Containerization
- **Nginx** - Reverse proxy
- **Ubuntu/Alpine** - Lightweight base images
- **docker-compose** - Orchestration

## 🔐 Security Features

- ✅ JWT authentication with refresh tokens
- ✅ Role-based access control (RBAC)
- ✅ Password hashing with bcrypt & Argon2
- ✅ Environment-based secrets management
- ✅ CORS protection
- ✅ Rate limiting (Nginx + middleware)
- ✅ Security headers (CSP, HSTS, X-Frame-Options)
- ✅ SQL injection prevention (ORM)
- ✅ XSS protection
- ✅ HTTPS/SSL support
- ✅ Session management with token revocation

## 📊 API Endpoints

```
# Authentication
POST   /api/v1/auth/login              - User login
POST   /api/v1/auth/logout             - User logout
GET    /api/v1/auth/me                 - Get current user
POST   /api/v1/auth/change-password    - Change password
GET    /api/v1/health                  - Health check

# Dashboard
GET    /api/v1/dashboard/summary       - Dashboard overview
GET    /api/v1/dashboard/charts        - Chart data

# Alerts & Incidents
GET    /api/v1/alerts                  - List alerts
POST   /api/v1/alerts                  - Create alert
GET    /api/v1/attacks                 - Attack map data

# Users & Audit
GET    /api/v1/users                   - List users
POST   /api/v1/audit                   - Log action
GET    /api/v1/audit                   - Audit history

# WebSocket
WS     /ws                             - Real-time alerts stream
```

## 🚀 Deployment Checklist

Before going to production, ensure:

### Security
- [ ] Generate strong SECRET_KEY
- [ ] Set strong database passwords
- [ ] Set strong OpenSearch password
- [ ] Configure CORS origins
- [ ] Obtain SSL certificates
- [ ] Review security headers

### Infrastructure
- [ ] Allocate adequate resources (CPU, RAM, disk)
- [ ] Set up automated backups
- [ ] Configure monitoring/alerting
- [ ] Test disaster recovery
- [ ] Set up log aggregation
- [ ] Configure firewall rules

### Application
- [ ] Set DEBUG=false
- [ ] Set ENV=production
- [ ] Set MOCK_OPENSEARCH=false
- [ ] Test all endpoints
- [ ] Load test application
- [ ] Create initial admin user

## 📈 Performance Tuning

### Database
```python
# Connection pool settings (in config.py)
pool_size = 20
max_overflow = 10
pool_pre_ping = True
```

### Nginx
- Worker connections: 2048
- Gzip compression enabled
- Connection pooling to backend
- Rate limiting configured

### Application
- Uvicorn workers: 4 (configurable)
- Async everywhere
- Proper connection handling

## 🔄 Maintenance

### Daily
- Monitor system resources
- Check application logs
- Verify all services running

### Weekly
- Review security logs
- Check database growth
- Test backup procedures

### Monthly
- Full security audit
- Performance review
- Update dependencies
- SSL certificate check

## 📚 Documentation

- [DEPLOYMENT.md](./DEPLOYMENT.md) - Detailed deployment guide
- [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md) - All improvements made
- [API Documentation](http://localhost/docs) - Swagger/OpenAPI
- [Environment Configuration](./.env.example) - All environment variables

## 🆘 Troubleshooting

### Services won't start
```bash
# Check logs
docker-compose logs backend
docker-compose logs db

# Verify environment
cat .env

# Check ports
netstat -tulpn | grep LISTEN
```

### Connection issues
```bash
# Test database
docker-compose exec db psql -U postgres -d mini_soc -c "SELECT 1"

# Test Redis
docker-compose exec redis redis-cli ping

# Test API
curl http://localhost/api/v1/health
```

## 📦 Environment Variables

All environment variables are documented in `.env.development` and `.env.production`.

### Critical Variables (Must Change)
- `SECRET_KEY` - JWT signing key
- `POSTGRES_PASSWORD` - Database password
- `OPENSEARCH_PASSWORD` - OpenSearch password
- `BACKEND_CORS_ORIGINS` - Allowed frontend domains

## 🤝 Contributing

This project is configured to be easily deployable. Key improvements made:

1. **Separated Dev/Prod Configs** - No more hardcoded secrets
2. **Production Dockerfile** - Multi-stage, optimized build
3. **Graceful Shutdown** - Proper signal handling
4. **Health Checks** - Built-in monitoring
5. **Documentation** - Complete deployment guide

## 📝 License

[Your License Here]

## 📞 Support

For deployment issues:
1. Check [DEPLOYMENT.md](./DEPLOYMENT.md)
2. Review application logs
3. Check [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md)

---

**Current Status:** 🟢 70% Production-Ready  
**Last Updated:** 2024-05-22  
**Version:** 1.0.0
