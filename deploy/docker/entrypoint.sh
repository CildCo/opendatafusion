#!/usr/bin/env bash
set -euo pipefail
ROLE="${ODF_ROLE:-api}"
case "$ROLE" in
  api)
    exec python -m uvicorn odf.main:app --host 0.0.0.0 --port "${ODF_API_PORT:-18080}" \
      --workers "${ODF_WEB_CONCURRENCY:-1}"
    ;;
  mcp)
    exec python -m odf.mcp.http
    ;;
  worker)
    export ODF_WORKER_ID="${ODF_WORKER_ID:-worker-$(hostname)}"
    exec python -m odf.worker
    ;;
  scheduler)
    exec python -m odf.scheduler
    ;;
  migrate)
    exec alembic upgrade head
    ;;
  prune)
    export ODF_APP_DIR=/app/impl ODF_PYTHON=python
    exec /app/scripts/prune-audit.sh
    ;;
  *)
    echo "unknown ODF_ROLE: $ROLE" >&2
    exit 2
    ;;
esac
