# REST & WebSocket API Specification Blueprint
## Enterprise Mini SOC Platform

### 1. API Conventions
- **Base Endpoint URL:** `/api/v1`
- **Authentication:** `Bearer <JWT_TOKEN>` in `Authorization` HTTP Header.
- **Content Type:** `application/json`
- **Error Response Structure:** Standardized RFC 7807 JSON.

```json
{
  "error_code": "RESOURCE_NOT_FOUND",
  "message": "Incident with ID 'INC-2026-0842' does not exist.",
  "timestamp": "2026-08-04T09:18:00Z",
  "path": "/api/v1/incidents/INC-2026-0842"
}
```

---

### 2. Core Endpoint Specifications

#### 2.1 Authentication & User Authorization
- `POST /api/v1/auth/login`
  - **Body:** `{ "username": "string", "password": "string" }`
  - **Response:** `{ "access_token": "jwt...", "token_type": "bearer", "user": { "id": "uuid", "role": "SOC_Analyst_T2" } }`

#### 2.2 Security Alert Management
- `GET /api/v1/alerts`
  - **Query Params:** `severity` (`CRITICAL`,`HIGH`), `page` (int), `limit` (int), `search` (string)
  - **Response:** Paginated list of enriched alerts.
- `WS /api/v1/alerts/ws`
  - **WebSocket Handshake:** Query param `?token=<jwt_access_token>`
  - **Protocol:** Real-time push of alert JSON payloads as ingested.

#### 2.3 Threat Intelligence Lookups
- `GET /api/v1/threat-intel/lookup/{ioc_type}/{ioc_value}`
  - **Example:** `/api/v1/threat-intel/lookup/ip/198.51.100.42`
  - **Response:** Combined reputation score, GeoIP info, VirusTotal detection stats, AbuseIPDB confidence score.

#### 2.4 Incident Management
- `GET /api/v1/incidents` - List incidents with filtering.
- `POST /api/v1/incidents` - Create new incident.
- `PATCH /api/v1/incidents/{incident_id}/status` - Transition incident state (`IN_PROGRESS`, `CONTAINED`, `RESOLVED`).

#### 2.5 SOAR Playbooks & Approvals
- `POST /api/v1/soar/playbooks/execute`
  - **Body:** `{ "playbook_id": "PB_FIREWALL_BLOCK", "target_ip": "198.51.100.42", "incident_id": "INC-01" }`
  - **Response:** `{ "execution_id": "exec-102", "status": "PENDING_APPROVAL" }`
- `POST /api/v1/soar/approvals/{approval_id}/decision`
  - **Body:** `{ "decision": "APPROVED", "reason": "Verified malicious SSH brute force attack" }`
