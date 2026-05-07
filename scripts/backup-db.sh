#!/bin/bash
# Полный дамп ConnectMe PostgreSQL в ./backups/.
# Кладите в crontab хоста, например:
#   0 3 * * * /opt/connectme/scripts/backup-db.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

source .env

BACKUP_DIR="${PROJECT_ROOT}/backups"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/connectme_${STAMP}.sql.gz"

docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
    pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$OUT"

echo "✅ Backup: $OUT ($(du -h "$OUT" | cut -f1))"

# Ротация — оставляем 14 последних
ls -1t "$BACKUP_DIR"/connectme_*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -v
