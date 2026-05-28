#!/bin/bash
#
# PostgreSQL Restore Script
# Restore from backup with safety checks
#

set -euo pipefail

# Configuration
BACKUP_FILE="${1:-}"
POSTGRES_HOST="${POSTGRES_SERVER:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-mini_soc}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"

if [ -z "${BACKUP_FILE}" ]; then
  echo "Usage: $0 <backup_file>"
  echo "Example: $0 /backups/mini-soc-20240115-120000.sql.gz"
  exit 1
fi

if [ ! -f "${BACKUP_FILE}" ]; then
  echo "Error: Backup file not found: ${BACKUP_FILE}"
  exit 1
fi

# Verify checksum if available
if [ -f "${BACKUP_FILE}.sha256" ]; then
  echo "[$(date)] Verifying checksum..."
  sha256sum -c "${BACKUP_FILE}.sha256"
fi

# Confirmation
echo "WARNING: This will REPLACE the current database: ${POSTGRES_DB}"
echo "Backup file: ${BACKUP_FILE}"
read -p "Are you sure? (yes/no): " CONFIRM

if [ "${CONFIRM}" != "yes" ]; then
  echo "Restore cancelled"
  exit 0
fi

# Create backup of current database before restore
SAFETY_BACKUP="/tmp/mini-soc-pre-restore-$(date +%Y%m%d-%H%M%S).sql.gz"
echo "[$(date)] Creating safety backup: ${SAFETY_BACKUP}"
pg_dump \
  -h "${POSTGRES_HOST}" \
  -p "${POSTGRES_PORT}" \
  -U "${POSTGRES_USER}" \
  -d "${POSTGRES_DB}" \
  --format=custom \
  --compress=9 \
  --file="${SAFETY_BACKUP}"

echo "[$(date)] Safety backup created: ${SAFETY_BACKUP}"

# Decrypt if encrypted
RESTORE_FILE="${BACKUP_FILE}"
if [[ "${BACKUP_FILE}" == *.enc ]]; then
  echo "[$(date)] Decrypting backup..."
  RESTORE_FILE="/tmp/restore-$(basename ${BACKUP_FILE} .enc)"
  openssl enc -aes-256-cbc -d \
    -in "${BACKUP_FILE}" \
    -out "${RESTORE_FILE}" \
    -pass "pass:${ENCRYPTION_KEY}"
fi

# Drop and recreate database
echo "[$(date)] Dropping database: ${POSTGRES_DB}"
psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};"

echo "[$(date)] Creating database: ${POSTGRES_DB}"
psql -h "${POSTGRES_HOST}" -p "${POSTGRES_PORT}" -U "${POSTGRES_USER}" -d postgres -c "CREATE DATABASE ${POSTGRES_DB};"

# Restore
echo "[$(date)] Restoring from backup..."
pg_restore \
  -h "${POSTGRES_HOST}" \
  -p "${POSTGRES_PORT}" \
  -U "${POSTGRES_USER}" \
  -d "${POSTGRES_DB}" \
  --verbose \
  --no-owner \
  --no-acl \
  "${RESTORE_FILE}"

# Cleanup decrypted temp file
if [ "${RESTORE_FILE}" != "${BACKUP_FILE}" ]; then
  rm -f "${RESTORE_FILE}"
fi

echo "[$(date)] Restore completed successfully"
echo "[$(date)] Safety backup available at: ${SAFETY_BACKUP}"
