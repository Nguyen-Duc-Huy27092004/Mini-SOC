# Architecture Decision Records (ADR)
## Enterprise Mini SOC Platform

### ADR-001: Selection of Modular Monolith Architecture
- **Decision:** Adopt a Modular Monolith architecture in FastAPI rather than distributed microservices for v1.0.0.
- **Reason:** Keeps deployment and operational overhead minimal for SME infrastructure while enforcing strict domain boundary isolation in code.
- **Alternative:** Distributed Microservices (gRPC / Kubernetes).
- **Trade-off:** High deployment simplicity vs. inability to scale single services independently (mitigated by async tasks and Redis event queues).

### ADR-002: Mandatory Human Approval Gate for SOAR Destructive Actions (BR-001)
- **Decision:** All playbooks taking destructive containment actions (IP blocking, host isolation, account lockout) MUST pause execution and request human manager approval.
- **Reason:** Prevents false-positive automation from causing operational downtime or blocking legitimate business traffic.
- **Alternative:** Full autonomous execution based on AI confidence score.
- **Trade-off:** Slight delay in containment vs 100% protection against accidental self-inflicted denial of service.

### ADR-003: Redis PubSub & Caching Layer for Ingestion & Threat Intel
- **Decision:** Use Redis 7 for high-speed alert broadcasting via PubSub and 24-hour caching of external Threat Intel API responses.
- **Reason:** Reduces external API key usage costs/rate-limit violations and protects PostgreSQL from lock contention under alert spikes.
