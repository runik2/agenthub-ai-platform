#!/usr/bin/env sh
set -eu

# Usage:
#   DATABASE_HOST=db DATABASE_PORT=5432 DATABASE_NAME=agenthub \
#   DATABASE_USER=agenthub PGPASSWORD='...' BACKUP_DIR=/var/backups/agenthub \
#   ./ops/backup-postgres.sh

DATABASE_HOST="${DATABASE_HOST:-db}"
DATABASE_PORT="${DATABASE_PORT:-5432}"
DATABASE_NAME="${DATABASE_NAME:-agenthub}"
DATABASE_USER="${DATABASE_USER:-agenthub}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="$BACKUP_DIR/agenthub-$timestamp.dump"

pg_dump \
  --host="$DATABASE_HOST" \
  --port="$DATABASE_PORT" \
  --username="$DATABASE_USER" \
  --dbname="$DATABASE_NAME" \
  --format=custom \
  --no-owner \
  --file="$target"

find "$BACKUP_DIR" -type f -name 'agenthub-*.dump' -mtime "+$RETENTION_DAYS" -delete
printf 'Created %s\n' "$target"
