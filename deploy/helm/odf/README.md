# ODF Helm chart

## Requirements

- Kubernetes 1.25+
- An RWX StorageClass if `persistence.enabled=true`; otherwise use the S3
  file backend and set `persistence.enabled=false`.
- A Secret (or `secrets.create=true` values) containing:
  - `ODF_DATABASE_URL`
  - `ODF_JWT_SECRET`
  - `ODF_FERNET_KEY`

## Install

```bash
helm upgrade --install odf deploy/helm/odf \
  --namespace odf --create-namespace \
  --set image.repository=ghcr.io/CildCo/opendatafusion \
  --set image.tag=1.0.0 \
  --set secrets.existingSecret=odf-secrets \
  --set ingress.enabled=true --set ingress.host=odf.example.com
```

The pre-install/pre-upgrade hook runs `alembic upgrade head`. The scheduler
runs one replica and relies on the PostgreSQL advisory lock; workers scale
horizontally with `SKIP LOCKED`.

## Backups

Set `backup.enabled=true` and optionally `auditPrune.enabled=true`. The backup
CronJob uses the `postgres:16-alpine` image (pg_dump 16) and writes pg_dump +
files archives with SHA-256 sidecars to the backup PVC. The audit CronJob uses
the application image and prunes rows older than `auditPrune.retentionDays`.

## Scaling

- `api.replicas`: behind the Service, readiness `/readyz`.
- `worker.replicas`: safe to increase.
- `scheduler.replicas` is fixed at 1 by design.
- MCP can be scaled, but restrict the Service to trusted networks.
