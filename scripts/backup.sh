#!/bin/bash
#
# Automated PostgreSQL Backup Script
# Production-grade backup with compression, encryption, and S3 upload
#

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backups}"
POSTGRES_HOST="${POSTGRES_SERVER:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-mini_soc}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
S3_BUCKET="${S3_BUCKET:-}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"

# Timestamp
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="mini-soc-${TIMESTAMP}.sql.gz"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting backup: ${BACKUP_FILE}"

# Dump database with compression
pg_dump \
  -h "${POSTGRES_HOST}" \
  -p "${POSTGRES_PORT}" \
  -U "${POSTGRES_USER}" \
  -d "${POSTGRES_DB}" \
  --format=custom \
  --compress=9 \
  --verbose \
  --file="${BACKUP_PATH}.tmp"

# Encrypt if key provided
if [ -n "${ENCRYPTION_KEY}" ]; then
  echo "[$(date)] Encrypting backup..."
  openssl enc -aes-256-cbc \
    -salt \
    -in "${BACKUP_PATH}.tmp" \
    -out "${BACKUP_PATH}.enc" \
    -pass "pass:${ENCRYPTION_KEY}"
  rm "${BACKUP_PATH}.tmp"
  BACKUP_PATH="${BACKUP_PATH}.enc"
else
  mv "${BACKUP_PATH}.tmp" "${BACKUP_PATH}"
fi

# Calculate checksum
sha256sum "${BACKUP_PATH}" > "${BACKUP_PATH}.sha256"

echo "[$(date)] Backup created: ${BACKUP_PATH}"
echo "[$(date)] Size: $(du -h "${BACKUP_PATH}" | cut -f1)"

# Upload to S3 if configured
if [ -n "${S3_BUCKET}" ]; then
  echo "[$(date)] Uploading to S3: ${S3_BUCKET}"
  aws s3 cp "${BACKUP_PATH}" "s3://${S3_BUCKET}/backups/"
  aws s3 cp "${BACKUP_PATH}.sha256" "s3://${S3_BUCKET}/backups/"
  echo "[$(date)] Upload complete"
fi

# Cleanup old backups
echo "[$(date)] Cleaning up backups older than ${RETENTION_DAYS} days"
find "${BACKUP_DIR}" -name "mini-soc-*.sql.gz*" -mtime +${RETENTION_DAYS} -delete

echo "[$(date)] Backup completed successfully"

# Verify backup integrity
echo "[$(date)] Verifying backup integrity..."
if [ -f "${BACKUP_PATH}.enc" ]; then
  # Decrypt and test
  openssl enc -aes-256-cbc -d \
    -in "${BACKUP_PATH}" \
    -pass "pass:${ENCRYPTION_KEY}" | \
    pg_restore --list > /dev/null
else
  pg_restore --list "${BACKUP_PATH}" > /dev/null
fi

echo "[$(date)] Backup verification passed"
