#!/usr/bin/env bash
set -euo pipefail
ARCHIVE="${1:-}"
DB_URL="${ODF_DATABASE_URL:-${DATABASE_URL:-}}"
FILES="${ODF_FILE_DIR:-/data/odf/files}"
if [ -z "$ARCHIVE" ] || [ ! -f "$ARCHIVE" ]; then
  echo "usage: restore.sh <archive.tar.gz> [--yes]" >&2
  exit 1
fi
if [ "${2:-}" != "--yes" ]; then
  echo "This overwrites the database and $FILES. Re-run with --yes." >&2
  exit 1
fi
if [ -z "$DB_URL" ]; then
  echo "ODF_DATABASE_URL is required" >&2
  exit 1
fi
if [ -f "$ARCHIVE.sha256" ]; then
  sha256sum -c "$ARCHIVE.sha256"
fi
PG_URL="${DB_URL/postgresql+psycopg/postgresql}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
tar -xzf "$ARCHIVE" -C "$WORK"
psql "$PG_URL" -v ON_ERROR_STOP=1 -f "$WORK/db.sql"
if [ -d "$WORK/files" ]; then
  mkdir -p "$FILES"
  cp -a "$WORK/files/." "$FILES/"
fi
echo "restore complete"
