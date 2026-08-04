# Wazuh Custom Rules & Decoders Blueprint
## Enterprise Mini SOC Platform

### 1. Custom Wazuh Rules XML (`rules/custom_mini_soc_rules.xml`)

```xml
<group name="mini_soc_detection,">

  <!-- Rule 100201: Web Brute Force Attack Detection -->
  <rule id="100201" level="10">
    <if_sid">31100</if_sid>
    <match>/admin/login|/api/v1/auth/login</match>
    <description>Mini SOC: Multiple Web Login Failures Detected from $(srcip)</description>
    <mitre>
      <id>T1110.001</id>
      <tactic>Credential Access</tactic>
      <technique>Password Guessing</technique>
    </mitre>
    <group>credential_access,pci_dss_10.2.4,</group>
  </rule>

  <!-- Rule 100202: Privilege Escalation Attempt (sudo) -->
  <rule id="100202" level="12">
    <if_sid>5402</if_sid>
    <match>sudo: auth failure|COMMAND=/bin/bash</match>
    <description>Mini SOC: Privilege Escalation / Unauthorized Sudo Attempt by $(dstuser)</description>
    <mitre>
      <id>T1548.003</id>
      <tactic>Privilege Escalation</tactic>
      <technique>Sudo and Sudo Caching</technique>
    </mitre>
    <group>privilege_escalation,</group>
  </rule>

  <!-- Rule 100203: Web Shell / Reverse Shell Command Execution -->
  <rule id="100203" level="14">
    <if_sid>100001</if_sid>
    <match>nc -e /bin/sh|/dev/tcp/|python -c 'import socket</match>
    <description>Mini SOC: CRITICAL - Reverse Shell Execution Detected on $(hostname)</description>
    <mitre>
      <id>T1059.004</id>
      <tactic>Execution</tactic>
      <technique>Unix Shell</technique>
    </mitre>
    <group>execution,critical_threat,</group>
  </rule>

</group>
```

---

### 2. Detection Rule Specification Table

| Rule ID | Severity Level | MITRE Tactic | MITRE Technique | False Positive Mitigation |
| :--- | :---: | :--- | :--- | :--- |
| **100201** | High (10) | Credential Access | T1110.001 (Password Guessing) | Whitelist internal admin subnet IP range. |
| **100202** | High (12) | Privilege Escalation | T1548.003 (Sudo Caching) | Exclude authorized Ansible deployment service account. |
| **100203** | Critical (14) | Execution | T1059.004 (Unix Shell) | Zero false positive tolerance for unapproved `nc -e` commands. |
