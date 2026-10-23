#!/usr/bin/env bash
set -euo pipefail
if [ -z "${ODF_DATABASE_URL:-}" ] && [ -r /opt/odf/.env ]; then
  set -a; . /opt/odf/.env; set +a
fi
DAYS="${ODF_AUDIT_RETENTION_DAYS:-180}"
OUT="${ODF_BACKUP_DIR:-/backups/odf}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT" "$OUT/audit"
APP_DIR="${ODF_APP_DIR:-/opt/odf/impl}"
PYTHON="${ODF_PYTHON:-/opt/odf/venv/bin/python}"
cd "$APP_DIR"
"$PYTHON" -m odf.cli prune-audit --days "$DAYS" \
  --export "$OUT/audit/audit-$STAMP.jsonl" --apply
find "$OUT/audit" -name 'audit-*.jsonl' -mtime +"${ODF_AUDIT_KEEP_DAYS:-365}" \
  -delete 2>/dev/null || true
