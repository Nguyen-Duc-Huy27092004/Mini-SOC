# SOAR Playbooks & Automation Specification
## Enterprise Mini SOC Platform

### 1. Playbook Standard Structure
Every SOAR Playbook specification MUST define:
1. **Trigger:** Event condition.
2. **Condition / Whitelist Check:** Verifies target IP is not on internal whitelist (`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`).
3. **Approval Gate:** Human-in-the-loop sign-off (except for BR-001.1 DDoS Auto-Blocking).
4. **Action Execution:** Firewall & Nginx API invocation.
5. **Rollback Action:** Automatic or manual unblock execution.
6. **Audit Trail:** Mandatory entry in `audit_logs` database table.

---

### 2. Playbook 01: Firewall IP Block (`PB_FIREWALL_BLOCK`)
Requires SOC Manager approval for general security alerts.

---

### 3. Playbook 02: Instant Anti-DDoS Auto-Mitigation (`PB_DDOS_AUTO_BLOCK`)

```json
{
  "playbook_id": "PB_DDOS_AUTO_BLOCK",
  "name": "Instant Anti-DDoS Automatic IP Blocking",
  "description": "Exempt from approval wait time per BR-001.1 to protect infrastructure availability",
  "trigger": {
    "event_type": ["HTTP_FLOOD", "SYN_FLOOD", "UDP_FLOOD", "SLOWLORIS", "SURICATA_DDOS"],
    "confidence_score_min": 85
  },
  "approval_required": false,
  "action": {
    "module": "firewall_client",
    "method": "add_instant_block_rule",
    "params": {
      "ip": "${source_ip}",
      "reason": "Automated DDoS Mitigation - ${event_type}",
      "ttl_seconds": 86400
    }
  },
  "rollback": {
    "module": "firewall_client",
    "method": "remove_block_rule",
    "params": { "ip": "${source_ip}" }
  }
}
```
