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
# The drill dumps the Nessie database, stops Nessie, wipes the catalog
# schema, restores the dump and reads the table again. Iceberg data and
# metadata files stay in object storage, so only the catalog needs backing
# up; dropping the table through Trino would delete its metadata and make the
# restored pointer unreadable.
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
command -v python3 >/dev/null || die "python3 is required"
mkdir -p "$BACKUP_DIR"

sql() {
  python3 "$(dirname "$0")/trino_query.py" "$TRINO" "$TRINO_USER" "$1"
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
[ -n "$BEFORE" ] || die "empty row count from Trino"
printf 'rows=%s\n' "$BEFORE"

if [ "${DRILL_ALLOW_WIPE:-}" != "yes" ]; then
  die "set DRILL_ALLOW_WIPE=yes to wipe the catalog database as part of the drill"
fi

say "damage: wipe the catalog database"
kubectl -n "$NESSIE_NS" scale deploy/"$NESSIE_DEPLOY" --replicas=0
kubectl -n "$NESSIE_NS" wait --for=delete pod -l "app=$NESSIE_DEPLOY" \
  --timeout=180s >/dev/null 2>&1 || true
POD=$(pg_pod)
kubectl -n "$NESSIE_NS" exec "$POD" -- psql -U nessie -d nessie \
  -v ON_ERROR_STOP=1 \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
printf 'catalog database is empty\n'

say "restore"
kubectl -n "$NESSIE_NS" exec -i "$POD" -- \
  psql -U nessie -d nessie -v ON_ERROR_STOP=1 -q < "$DUMP" >/dev/null
kubectl -n "$NESSIE_NS" scale deploy/"$NESSIE_DEPLOY" \
  --replicas="${NESSIE_REPLICAS:-2}"
kubectl -n "$NESSIE_NS" rollout status deploy/"$NESSIE_DEPLOY" \
  --timeout=240s

say "row count after"
AFTER=$(sql "SELECT count(*) FROM $TABLE") || die "table did not come back"
printf 'rows=%s\n' "$AFTER"

if [ "$BEFORE" = "$AFTER" ]; then
  say "restore verified ($AFTER rows)"
else
  die "row count changed: $BEFORE -> $AFTER"
fi
