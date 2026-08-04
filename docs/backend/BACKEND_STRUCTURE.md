# Backend Clean Architecture & Module Layout
## Enterprise Mini SOC Platform

### 1. Source Directory Layout (`backend/app/`)

```
backend/app/
├── api/                    # API Routing Layer
│   ├── v1/                 # Version 1 Router Registrations
│   │   ├── auth.py         # Login, Refresh, Logout, User Me
│   │   ├── alerts.py       # Alert Grid, Filters, WebSocket Stream
│   │   ├── threat_intel.py # Reputation queries & GeoIP
│   │   ├── incidents.py    # Ticket CRUD & Status transition
│   │   ├── soar.py         # Playbook execution & approval gates
│   │   ├── ai.py           # AI summarization & root cause
│   │   └── health.py       # Liveness & Readiness checks
│   └── deps.py             # FastAPI Security Dependencies (Current User, RBAC)
│
├── core/                   # Infrastructure Core
│   ├── config.py           # Settings management (Pydantic BaseSettings)
│   ├── security.py         # Password hashing, JWT token creation & verification
│   ├── database.py         # SQLAlchemy 2.0 Async Session Engine & Pool
│   ├── redis.py            # Redis Client & PubSub Broker
│   └── logging.py          # Structured JSON Log Formatter
│
├── models/                 # SQLAlchemy 2.0 ORM Database Entities
│   ├── user.py             # User & Role Entities
│   ├── alert.py            # Alert & Rule Entities
│   ├── incident.py         # Incident & Ticket Entities
│   ├── soar.py             # Playbook & Approval Entities
│   └── audit.py            # AuditLog Entity
│
├── schemas/                # Pydantic V2 Request & Response DTOs
│   ├── auth.py             # UserLogin, Token, UserOut
│   ├── alert.py            # AlertIn, AlertOut, AlertFilter
│   ├── incident.py         # IncidentCreate, IncidentUpdate, IncidentOut
│   ├── soar.py             # PlaybookExecute, ApprovalDecision
│   └── common.py           # PaginatedResponse, StandardErrorResponse
│
├── services/               # Core Business Logic Layer (Clean Domain)
│   ├── auth_service.py     # Auth validation, password check, JWT sign
│   ├── alert_service.py    # Alert deduplication, status update
│   ├── ti_service.py       # Threat Intel query aggregator
│   ├── incident_service.py # Lifecycle state machine & SLA countdown
│   ├── soar_service.py     # Playbook workflow & approval gate validation
│   └── ai_service.py       # Prompt engineering & LLM integration
│
├── repositories/           # Database Access Layer (Data Access Only)
│   ├── base.py             # Generic CRUD Repository
│   ├── user_repo.py        # User DB queries
│   ├── alert_repo.py       # Alert DB queries with pagination & filtering
│   └── incident_repo.py    # Incident DB queries
│
├── workers/                # Async Background Workers (Redis / ARQ / Celery)
│   ├── wazuh_collector.py  # Ingestion stream reader for Wazuh alerts.json
│   ├── zabbix_poller.py    # Periodic Zabbix metrics polling task
│   └── ti_enricher.py      # Background threat intel enrichment worker
│
└── main.py                 # FastAPI Application Entrypoint & Middleware Setup
```
