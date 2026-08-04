# Database Backup & Disaster Recovery Specification
## Enterprise Mini SOC Platform

### 1. Automated Backup Strategy
- **Daily Automated Logical Backup:** `pg_dump` compressed custom format (`.dump`) taken at 02:00 UTC.
- **WAL Archiving (Point-In-Time Recovery - PITR):** Continuous Write-Ahead Logging archiving to backup directory.
- **RTO & RPO Objectives:**
  - **RPO (Recovery Point Objective):** < 15 minutes (via WAL streaming).
  - **RTO (Recovery Time Objective):** < 1 hour for full database restore.

---

### 2. Automated Backup Execution Script Example (`scripts/backup_db.sh`)

```bash
#!/usr/bin/env bash
set -eo pipefail

BACKUP_DIR="/var/backups/mini-soc"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME=${POSTGRES_DB:-minisoc}

mkdir -p "$BACKUP_DIR"
docker exec mini-soc-postgres pg_dump -U ${POSTGRES_USER:-minisoc} -Fc "$DB_NAME" > "$BACKUP_DIR/db_$DATE.dump"

# Retain daily backups for 30 days
find "$BACKUP_DIR" -type f -name "*.dump" -mtime +30 -delete
```
