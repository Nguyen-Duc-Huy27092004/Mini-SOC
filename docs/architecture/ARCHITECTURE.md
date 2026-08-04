# System Architecture Blueprint
## Enterprise Mini SOC Platform

### 1. Architectural Overview & Style
The **Enterprise Mini SOC Platform** follows a **Modular Monolith Architecture with Event-Driven Ingestion**. This design guarantees low operational complexity for deployment on single/dual hosts while retaining clean domain separation and horizontal scaling readiness (Microservices / Kubernetes compatible).

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend Layer (React 18 + TS)           │
│   Dashboard │ Live Alerts │ Incident Board │ SOAR Playbooks │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS / WSS (TLS 1.3)
┌──────────────────────────────┴──────────────────────────────┐
│                    Nginx Reverse Proxy                       │
│           (SSL Termination, Rate Limit, Security Headers)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / WS
┌──────────────────────────────┴──────────────────────────────┐
│               FastAPI Application Layer (Python 3.12)       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Auth/RBAC│  │ Alert Eng│  │ ThreatInt│  │   SOAR   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Incident │  │ AI Sec   │  │   Audit  │  │ Metrics  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└────────┬─────────────────────┬────────────────────┬─────────┘
         │                     │                    │
┌────────┴────────┐   ┌────────┴────────┐  ┌────────┴────────┐
│ PostgreSQL 16   │   │     Redis 7     │  │ External APIs   │
│ (Relational DB, │   │ (PubSub Queue & │  │ (Wazuh, Zabbix, │
│ Partitioning)   │   │  TI Cache Layer)│  │ VT, AbuseIPDB)  │
└─────────────────┘   └─────────────────┘  └─────────────────┘
```

---

### 2. Core Architectural Principles
- **Clean Architecture & Separation of Concerns:** Core domain business logic is decoupled from external APIs, ORMs, and web delivery layers.
- **High Cohesion & Low Coupling:** Modules communicate through explicit Python interfaces and Redis PubSub events.
- **Event-Driven Asynchronous Ingestion:** High-volume log events are ingested asynchronously into Redis PubSub queues to protect database writing performance.
- **Fail-Safe & Graceful Degradation:** If external threat intel APIs (VirusTotal/AbuseIPDB) fail, local caching and fallback heuristics ensure uninterrupted operations.

---

### 3. Subsystem Breakdown
1. **API & Web Delivery Subsystem:** FastAPI REST handlers, OpenAPI generation, WebSocket connection manager.
2. **Ingestion Subsystem:** Async Wazuh `alerts.json` log reader & Zabbix poller pushing normalized events to Redis.
3. **Enrichment & AI Subsystem:** GeoIP lookups, Threat Intel cache queries, AI natural language summarizer.
4. **SOAR Execution Subsystem:** Playbook engine, human-in-the-loop approval gate manager, firewall REST client.
5. **Persistence & Cache Subsystem:** PostgreSQL 16 (SQLAlchemy ORM + Alembic) and Redis 7 key-value cache.
