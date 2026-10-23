#!/usr/bin/env bash
set -euo pipefail
OUT="${1:-./backups}"
if [ -z "${ODF_DATABASE_URL:-}" ] && [ -r /opt/odf/.env ]; then
  set -a; . /opt/odf/.env; set +a
fi
DB_URL="${ODF_DATABASE_URL:-${DATABASE_URL:-}}"
FILES="${ODF_FILE_DIR:-/data/odf/files}"
if [ -z "$DB_URL" ]; then
  echo "ODF_DATABASE_URL is required" >&2
  exit 1
fi
if ! command -v pg_dump >/dev/null 2>&1; then
  for d in /opt/pgsql*/bin /usr/pgsql*/bin /usr/lib/postgresql/*/bin; do
    [ -x "$d/pg_dump" ] && PATH="$d:$PATH"
  done
  export PATH
fi
for cmd in pg_dump tar sha256sum; do
  command -v "$cmd" >/dev/null || { echo "missing $cmd" >&2; exit 1; }
done
PG_URL="${DB_URL/postgresql+psycopg/postgresql}"
mkdir -p "$OUT"
STAMP="$(date +%Y%m%d-%H%M%S)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
pg_dump --no-owner --no-privileges "$PG_URL" > "$WORK/db.sql"
if [ -d "$FILES" ]; then
  cp -a "$FILES" "$WORK/files"
fi
ARCHIVE="$OUT/odf-$STAMP.tar.gz"
tar -czf "$ARCHIVE" -C "$WORK" .
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
KEEP="${ODF_BACKUP_KEEP:-14}"
if [ "$KEEP" -gt 0 ] 2>/dev/null; then
  { ls -1t "$OUT"/odf-*.tar.gz 2>/dev/null || true; } |     tail -n +$((KEEP + 1)) |     while read -r old; do rm -f "$old" "$old.sha256"; done
fi
echo "backup: $ARCHIVE"
