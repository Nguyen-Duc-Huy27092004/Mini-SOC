# Module & Domain Architecture Design
## Enterprise Mini SOC Platform

### 1. Domain Module Layout

The backend source code in `backend/app/` is structured into explicit domain modules:

```
backend/app/
├── core/                   # Shared Infrastructure & Configuration
│   ├── config.py           # Environment variables (Pydantic Settings)
│   ├── security.py         # Password hashing, JWT token generation & verification
│   ├── database.py         # SQLAlchemy async engine & connection session pool
│   ├── redis.py            # Redis connection pool & PubSub manager
│   └── exceptions.py       # Global standardized exception handlers
│
├── modules/
│   ├── auth/               # Authentication & User Management Domain
│   │   ├── models.py       # SQLAlchemy User & Role models
│   │   ├── schemas.py      # Pydantic V2 auth request/response schemas
│   │   ├── services.py     # Auth service & RBAC verification
│   │   └── router.py       # FastAPI auth endpoints (/api/v1/auth)
│   │
│   ├── alerts/             # Security Alert Ingestion & Monitoring Domain
│   │   ├── models.py       # Alert & AlertRule models
│   │   ├── schemas.py      # Alert DTO schemas
│   │   ├── collector.py    # Async log stream collector (Wazuh & Zabbix)
│   │   ├── services.py     # Deduplication & enrichment logic
│   │   └── router.py       # Alert endpoints & WebSocket stream (/api/v1/alerts)
│   │
│   ├── threat_intel/       # Threat Intelligence & GeoIP Domain
│   │   ├── models.py       # IOC Cache & GeoIP models
│   │   ├── services.py     # VT, AbuseIPDB, GeoIP lookup service
│   │   └── router.py       # Threat Intel endpoints (/api/v1/threat-intel)
│   │
│   ├── incidents/          # Incident Lifecycle & SLA Domain
│   │   ├── models.py       # Incident, Ticket, SLA models
│   │   ├── services.py     # Lifecycle state machine & SLA countdown logic
│   │   └── router.py       # Incident CRUD endpoints (/api/v1/incidents)
│   │
│   ├── soar/               # Automated Response & Playbook Domain
│   │   ├── models.py       # Playbook, ExecutionLog, ApprovalGate models
│   │   ├── services.py     # Playbook execution engine & firewall clients
│   │   └── router.py       # Playbook execution & approval (/api/v1/soar)
│   │
│   ├── ai_assistant/       # AI Correlation & Risk Scoring Domain
│   │   ├── services.py     # AI Summarizer, Correlation, Risk Scoring
│   │   └── router.py       # AI endpoints (/api/v1/ai)
│   │
│   └── audit/              # Immutable Audit Logging Domain
│       ├── models.py       # AuditLog model
│       ├── middleware.py   # HTTP audit interceptor middleware
│       └── services.py     # Audit writing service
```

---

### 2. Module Communication Rules
1. Modules MUST communicate via Service classes or Async Redis PubSub events—NEVER via direct ORM cross-module model queries.
2. Circular dependencies between modules are strictly forbidden.
3. Every FastAPI endpoint router MUST depend on Pydantic V2 request/response schemas.
