# Component Architecture & Interfaces
## Enterprise Mini SOC Platform

### 1. Component Interfaces

#### 1.1 `AlertCollectorInterface`
- **Responsibilities:** Interface for background services consuming log events from Wazuh and Zabbix.
- **Methods:**
  - `async start_stream() -> None`
  - `async process_alert(alert_raw: dict) -> AlertEnriched`

#### 1.2 `ThreatIntelProviderInterface`
- **Responsibilities:** Interface for external threat intelligence reputation queries.
- **Methods:**
  - `async lookup_ip(ip_address: str) -> ThreatIntelReport`
  - `async lookup_hash(file_hash: str) -> ThreatIntelReport`

#### 1.3 `SOARPlaybookExecutorInterface`
- **Responsibilities:** Interface for SOAR action execution handlers.
- **Methods:**
  - `async validate_params(params: dict) -> bool`
  - `async execute(params: dict) -> PlaybookResult`
  - `async rollback(params: dict) -> PlaybookResult`
