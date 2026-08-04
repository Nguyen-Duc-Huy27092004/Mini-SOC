# Deployment & Infrastructure Architecture
## Enterprise Mini SOC Platform

### 1. Production Docker Container Topology

```
┌─────────────────────────────────────────────────────────────┐
│                       Nginx (Host Port 80/443)              │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
┌──────────────┴──────────────┐┌──────────────┴──────────────┐
│  frontend (React Static UI) ││  backend (FastAPI App Server)│
│  Port 80 (Internal Docker)  ││  Port 8000 (Internal Docker) │
└─────────────────────────────┘└──────────────┬───────────────┘
                                              │
                               ┌──────────────┴──────────────┐
                               │  redis (Cache & PubSub)     │
                               │  Port 6379 (Internal Docker)│
                               └──────────────┬───────────────┘
                                              │
                               ┌──────────────┴──────────────┐
                               │  postgres (PostgreSQL 16)   │
                               │  Port 5432 (Internal Docker)│
                               └─────────────────────────────┘
```

---

### 2. Environment Isolation & Security Configuration
- **Container Network:** Private internal bridge network (`mini-soc-network`).
- **Secret Isolation:** Environment secrets injected via `.env` / Docker secret files (NEVER hardcoded in source files).
- **Resource Limits:**
  - `backend`: max 2 CPU cores, 2GB RAM
  - `postgres`: max 2 CPU cores, 2GB RAM
  - `redis`: max 1 CPU core, 1GB RAM
  - `frontend` & `nginx`: max 1 CPU core, 512MB RAM
