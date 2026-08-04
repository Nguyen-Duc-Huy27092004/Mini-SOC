# Risk Analysis & Mitigation Matrix
## Enterprise Mini SOC Platform

### 1. Risk Evaluation Framework

Risks are rated by Impact (1-5) and Likelihood (1-5) yielding a Risk Score (1-25).

| Risk ID | Category | Risk Description | Impact | Likelihood | Risk Score | Mitigation Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **RSK-001** | Technical | High volume log spikes overload FastAPI ingestion service. | 5 | 4 | **20 (HIGH)** | Implement Redis PubSub queue, async workers, rate limiting, and PostgreSQL table partitioning. |
| **RSK-002** | Security | Autonomous SOAR action accidentally blocks legitimate corporate IP or critical server. | 5 | 3 | **15 (HIGH)** | Mandatory human approval gate (BR-001) for all destructive actions; IP whitelist verification. |
| **RSK-003** | Operational | External Threat Intel APIs (VirusTotal/AbuseIPDB) hit rate limits or go offline. | 3 | 4 | **12 (MED)** | Redis 24h caching layer + graceful degradation allowing pipeline to proceed with warning badges. |
| **RSK-004** | Security | WebSocket connection hijacked allowing unauthorized eavesdropping on SOC alerts. | 4 | 2 | **8 (MED)** | Mandatory WSS (TLS 1.3), JWT token validation in WebSocket handshake query, strict CORS policy. |
| **RSK-005** | Compliance | Failure to audit analyst actions violating regulatory requirements. | 4 | 2 | **8 (MED)** | Centralized audit logger intercepting all HTTP & WebSocket operations into immutable database tables. |
