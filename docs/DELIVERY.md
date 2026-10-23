# Container and Kubernetes delivery

## Image

`deploy/docker/Dockerfile` builds one image that serves four roles selected by
`ODF_ROLE`:

| Role | Command |
| --- | --- |
| `api` | uvicorn on `ODF_API_PORT` (default 18080) |
| `mcp` | streamable HTTP MCP on `ODF_MCP_PORT` (default 18082) |
| `worker` | durable job worker; worker id defaults to `worker-<hostname>` |
| `scheduler` | cron scheduler leader (PostgreSQL advisory lock) |
| `migrate` | `alembic upgrade head` |
| `prune` | audit archive + retention prune |

The frontend is built in a Node stage and copied into `impl/odf/static`; there
is no separate web container. The runtime is unprivileged (uid/gid 10001),
root filesystem read-only, `/tmp` tmpfs, file storage on a volume.

Build:

```bash
docker build -f deploy/docker/Dockerfile -t odf:local .
```

## Docker Compose

```bash
cd deploy/docker
cp .env.example .env       # fill secrets
docker compose up -d --build
```

Services: PostgreSQL, one-shot migrate, API, MCP, worker, scheduler. Scale
workers with `docker compose up -d --scale worker=3`. The scheduler must remain
one replica; extra replicas exit because of the advisory lock.

Operations profile:

```bash
docker compose --profile ops run --rm backup
docker compose --profile ops run --rm audit-prune
```

Schedule those commands with host cron/journal timers. `backup` uses the
`postgres:16-alpine` image so `pg_dump` matches PostgreSQL 16.

## Helm

```bash
helm upgrade --install odf deploy/helm/odf \
  --namespace odf --create-namespace \
  --set image.repository=ghcr.io/CildCo/opendatafusion \
  --set image.tag=v1.0.0 \
  --set secrets.existingSecret=odf-secrets \
  --set ingress.enabled=true --set ingress.host=odf.example.com
```

- Migration runs as a pre-install/pre-upgrade Job.
- API, MCP, worker and scheduler share the file PVC; use an RWX storage class
  or the S3 backend with `persistence.enabled=false`.
- `scheduler.replicas` is intentionally fixed at 1.
- Optional backup and audit-prune CronJobs use a separate backup PVC.
- Readiness: API `/readyz`, MCP TCP 18082; liveness: API `/livez`.

Secrets must contain `ODF_DATABASE_URL`, `ODF_JWT_SECRET`, `ODF_FERNET_KEY`.
Alternatively set `secrets.create=true` with the three values (not recommended
for production GitOps).

## Release

`.github/workflows/release-image.yml` builds and pushes
`ghcr.io/<owner>/<repo>` on `v*` tags or manual dispatch. CI also runs
`helm lint` and `helm template` on every push.

Tag a release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Then install the chart with the matching image tag. Roll back with
`helm rollback odf`, which re-runs the migration hook (upgrade is expected to
be forward-only; restore a database backup for a schema downgrade).
