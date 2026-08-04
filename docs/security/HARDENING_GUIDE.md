# Infrastructure & Nginx Hardening Guide
## Enterprise Mini SOC Platform

### 1. Nginx Security Headers Configuration

```nginx
# Security Headers Configuration
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' wss:;" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
```

---

### 2. TLS Configuration Baseline
- **Protocol:** TLS 1.3 only (TLS 1.0, 1.1, and 1.2 disabled).
- **Ciphers:** `ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384`.
- **HSTS:** Enabled with 1-year duration (`max-age=31536000`).
