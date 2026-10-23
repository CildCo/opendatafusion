#!/bin/sh
# deploy/bootstrap.sh — run once on a new host; does not start services
set -eu
PY="${PYTHON:-python3}"
id odf >/dev/null 2>&1 || useradd -r -m -d /opt/odf odf
mkdir -p /opt/odf/impl /data/odf
cp -r impl/. /opt/odf/impl/
find /opt/odf/impl -maxdepth 1 \( -name .venv -o -name .env -o -name '*.db' \) -exec rm -rf {} +
find /opt/odf/impl -type d -name __pycache__ -prune -exec rm -rf {} +
$PY -m venv /opt/odf/venv
/opt/odf/venv/bin/pip install -U pip
/opt/odf/venv/bin/pip install -e /opt/odf/impl
install -m 600 /dev/null /opt/odf/.env
echo "fill /opt/odf/.env, run: cd /opt/odf/impl && /opt/odf/venv/bin/alembic upgrade head" >&2
echo "then: systemctl daemon-reload && systemctl enable --now odf-api" >&2
