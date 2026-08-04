# Business Logic & Service Design Specifications
## Enterprise Mini SOC Platform

### 1. Service Layer Principles
- **No DB Queries in Routers:** Routers only extract HTTP request params, invoke Pydantic validation, call a Service method, and return the Pydantic response model.
- **Service Domain Isolation:** `AlertService`, `IncidentService`, `SOARService`, and `AuthService` are completely decoupled.
- **Dependency Injection:** Database sessions (`AsyncSession`) and Redis pools are injected via FastAPI dependencies (`Depends(get_db)`).

---

### 2. Core Service Methods Blueprint

#### `AlertService`
```python
class AlertService:
    async def process_incoming_alert(self, raw_alert: dict) -> AlertOut:
        # 1. Deduplicate via Redis 60s sliding window
        # 2. Map MITRE ATT&CK technique & severity level
        # 3. Enrich IOCs via ThreatIntelService
        # 4. Persist to DB via AlertRepository
        # 5. Broadcast to WebSocket via Redis PubSub
```

#### `SOARService`
```python
class SOARService:
    async def initiate_playbook(self, playbook_id: str, target_ip: str, requester: User) -> ApprovalGateOut:
        # 1. Validate target IP & whitelist
        # 2. Per BR-001, create Approval Gate record (state=PENDING_APPROVAL)
        # 3. Notify SOC Managers via WebSocket
        # 4. Log audit entry
```
