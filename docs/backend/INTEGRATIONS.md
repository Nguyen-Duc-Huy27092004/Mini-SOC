# Integrations & External Client Wrappers
## Enterprise Mini SOC Platform

### 1. Wazuh API & Alert Log Stream Collector
- **Authentication:** Token-based HTTPS basic auth to Wazuh Manager API (`https://wazuh-manager:55000/security/user/authenticate`).
- **File Stream Monitoring:** Async tail worker reading `/var/ossec/logs/alerts/alerts.json`.

---

### 2. Threat Intelligence Provider Clients
- **VirusTotal API v3 Client:** `https://www.virustotal.com/api/v3/ip_addresses/{ip}`
- **AbuseIPDB v2 Client:** `https://api.abuseipdb.com/api/v2/check?ipAddress={ip}`
- **MaxMind GeoIP2 Reader:** Local `.mmdb` database reader fallback.
