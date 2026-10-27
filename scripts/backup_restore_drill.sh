#!/usr/bin/env bash
# Backup and restore drill for the lakehouse catalog.
#
# Run on the machine that holds the kubeconfig and can reach Trino.
#
#   TRINO=http://127.0.0.1:8080 \
#   TABLE=iceberg.demo.events \
#   NESSIE_NS=catalog NESSIE_PG_APP=nessie-postgres \
#   ./backup_restore_drill.sh
#
# The drill dumps the Nessie database, drops one table through Trino, restores
# the dump and reads the table again. Iceberg data files are immutable, so the
# catalog is the part that needs a backup; the files stay where they are.
set -euo pipefail

TRINO="${TRINO:-http://127.0.0.1:8080}"
SCHEMA="${SCHEMA:-demo}"
TABLE="${TABLE:-iceberg.demo.events}"
NESSIE_NS="${NESSIE_NS:-catalog}"
NESSIE_PG_APP="${NESSIE_PG_APP:-nessie-postgres}"
NESSIE_DEPLOY="${NESSIE_DEPLOY:-nessie}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/odf}"
TRINO_USER="${TRINO_USER:-odf}"

say() { printf '\n==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

command -v kubectl >/dev/null || die "kubectl is required"
mkdir -p "$BACKUP_DIR"

sql() {
  local query="$1" url payload
  url="$TRINO/v1/statement"
  payload=$(curl -s -X POST "$url" -H "X-Trino-User: $TRINO_USER" \
    -H "Content-Type: text/plain" --data-binary "$query")
  while :; do
    if printf '%s' "$payload" | grep -q '"error"'; then
      printf '%s' "$payload" | sed -n 's/.*"message":"\([^"]*\)".*/\1/p' >&2
      return 1
    fi
    next=$(printf '%s' "$payload" | sed -n 's/.*"nextUri":"\([^"]*\)".*/\1/p')
    printf '%s' "$payload" | sed -n 's/.*"data":\[\[\([^]]*\)\]\].*/\1/p'
    [ -z "$next" ] && return 0
    payload=$(curl -s "$next")
  done
}

pg_pod() {
  kubectl -n "$NESSIE_NS" get pods -l "app=$NESSIE_PG_APP" \
    -o jsonpath='{.items[0].metadata.name}'
}

say "backup $NESSIE_NS/$NESSIE_PG_APP"
POD=$(pg_pod)
STAMP=$(date +%Y%m%d-%H%M%S)
DUMP="$BACKUP_DIR/nessie-$STAMP.sql"
kubectl -n "$NESSIE_NS" exec "$POD" -- \
  pg_dump --clean --if-exists -U nessie nessie > "$DUMP"
printf 'wrote %s (%s)\n' "$DUMP" "$(du -h "$DUMP" | cut -f1)"

say "row count before"
BEFORE=$(sql "SELECT count(*) FROM $TABLE") || die "cannot read $TABLE"
printf 'rows=%s\n' "$BEFORE"

say "damage: drop $TABLE"
sql "DROP TABLE $TABLE" >/dev/null
if sql "SELECT count(*) FROM $TABLE" >/dev/null 2>&1; then
  die "table is still readable after DROP; aborting"
fi
printf 'table is gone\n'

say "restore"
kubectl -n "$NESSIE_NS" scale deploy/"$NESSIE_DEPLOY" --replicas=0
kubectl -n "$NESSIE_NS" wait --for=delete pod -l "app=$NESSIE_DEPLOY" \
  --timeout=120s >/dev/null 2>&1 || true
kubectl -n "$NESSIE_NS" exec -i "$(pg_pod)" -- \
  psql -U nessie -d nessie -q < "$DUMP" >/dev/null
kubectl -n "$NESSIE_NS" scale deploy/"$NESSIE_DEPLOY" --replicas=1
kubectl -n "$NESSIE_NS" rollout status deploy/"$NESSIE_DEPLOY" --timeout=180s

say "row count after"
AFTER=$(sql "SELECT count(*) FROM $TABLE") || die "table did not come back"
printf 'rows=%s\n' "$AFTER"

if [ "$BEFORE" = "$AFTER" ]; then
  say "restore verified ($AFTER rows)"
else
  die "row count changed: $BEFORE -> $AFTER"
fi
