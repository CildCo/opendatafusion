# Deployment

## Prerequisites

- PostgreSQL 14+ (control database).
- Python ≥ 3.11.
- Ports `18080` (HTTP API) and `18082` (MCP) free.

## Steps

```bash
sudo sh deploy/bootstrap.sh
sudo vi /opt/odf/.env          # fill ODF_DATABASE_URL / ODF_JWT_SECRET / ODF_FERNET_KEY
set -a; . /opt/odf/.env; set +a
cd /opt/odf/impl && sudo -u odf /opt/odf/venv/bin/alembic upgrade head
sudo cp deploy/systemd/odf-api.service /etc/systemd/system/
sudo cp deploy/systemd/odf-mcp.service /etc/systemd/system/
sudo cp deploy/systemd/odf-worker.service /etc/systemd/system/
sudo cp deploy/systemd/odf-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now odf-api odf-mcp odf-worker odf-scheduler
sudo cp deploy/systemd/odf-backup.* deploy/systemd/odf-audit-prune.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now odf-backup.timer odf-audit-prune.timer
```

MCP tools are exposed on `:18082` (streamable HTTP). Restrict this port to
trusted hosts with a firewall or security group. `pause_flow` and
`resume_flow` still require an approval token.

## Verify

```bash
curl -s http://127.0.0.1:18080/livez
curl -s http://127.0.0.1:18080/readyz
curl -s http://127.0.0.1:18080/docs | head
```

## Containers and Kubernetes

- Docker image: `deploy/docker/Dockerfile` (one image, role via `ODF_ROLE`).
- Compose stack: `deploy/docker/docker-compose.yml`; copy
  `deploy/docker/.env.example` to `.env` first.
- Helm chart: `deploy/helm/odf`; migrations run as a pre-install/pre-upgrade
  hook.

See `docs/DELIVERY.md` for build, scaling and release instructions.

## Resource budget

| Service | Budget |
|---|---|
| odf-api | 3 GB |
| odf-mcp | 512 MB |
| PostgreSQL | per database |

## Notes

- Do not run the test suite against a production control database. Set
  `ODF_TEST_DATABASE_URL` to an isolated test database.
- Backups belong outside the server; do not leave `.bak` or temporary
  archives on the host.
- Set `ODF_AKSK_ALLOW_SHA1=false` after clients migrate to HMAC-SHA256.
- Keep `ODF_FILE_SOURCE_ROOTS` narrow; file datasources cannot escape it.
- Set `ODF_HTTP_ALLOW_PRIVATE=false` (default) in untrusted networks and use
  `ODF_HTTP_ALLOWED_HOSTS=api.example.com,*.trusted.example` if needed.
