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

## Lakehouse data plane

`deploy/k8s/dataplane` installs the data plane the platform runs work on:
SeaweedFS S3, Nessie (Iceberg REST catalog), Trino, Kafka, a CDC PostgreSQL,
Debezium, Flink with its SQL Gateway, and Prometheus/Grafana.

```bash
cd deploy/k8s/dataplane
cp values.env.example values.env   # image tags, sizes, bucket
./install.sh
./make-kubeconfig.sh               # prints the control-plane settings
```

The installer is idempotent and creates every credential as a Kubernetes
Secret. Nothing in the repository contains an access key, password or token.

### Control-plane settings

| Variable | Purpose |
| --- | --- |
| `ODF_K8S_API_URL` | Kubernetes API endpoint |
| `ODF_K8S_TOKEN` | namespace-scoped service account token |
| `ODF_K8S_CA_FILE` | cluster CA bundle |
| `ODF_K8S_NAMESPACE` | namespace Spark applications are created in |
| `ODF_K8S_ALLOWED_IMAGES` | comma-separated image prefixes allowed for jobs |
| `ODF_FLINK_SQL_GATEWAY_URL` | Flink SQL Gateway REST base URL |
| `ODF_FLINK_REST_URL` | Flink JobManager REST base URL, used for job status |
| `ODF_ENGINE_SQL_WRITE_ENABLED` | allow non-read-only statements on `/engine/sql` |
| `ODF_ENGINE_JOB_TIMEOUT_S` | default pipeline engine-node timeout |

The service account from `60-control-plane-rbac.yaml` may create and delete
Spark applications and read pods in one namespace. It cannot read Secrets.

### Verification

```bash
ODF_API=http://<control-plane> ODF_USER=admin ODF_PASSWORD=... \
LAKE_DSN='trino://odf@<node>:8080/iceberg/demo' \
python scripts/acceptance_lakehouse.py
```

The script checks datasource creation, the Trino connection, schema creation,
Iceberg metadata sync, table listing, a Spark job reaching a terminal state,
Flink SQL through the gateway, engine job listing, audit records, and
cancellation. It exits non-zero on failure.

### Lakehouse profile

A Spark job submitted without a `spark_conf` still gets the Iceberg catalog
because the control plane applies a profile:

| Variable | Purpose |
| --- | --- |
| `ODF_LAKEHOUSE_ENABLED` | apply the profile at all |
| `ODF_LAKEHOUSE_CATALOG` | catalog name, default `iceberg` |
| `ODF_LAKEHOUSE_URI` | Nessie Iceberg REST endpoint |
| `ODF_LAKEHOUSE_WAREHOUSE` | warehouse identifier |
| `ODF_LAKEHOUSE_S3_ENDPOINT` | S3 endpoint for Spark writers |
| `ODF_SPARK_IMAGE` | image with the Iceberg runtime baked in |
| `ODF_SPARK_JARS` | fallback jar list when a custom image is not available |

`GET /api/v1/engine/profiles` returns the effective profile. Values a caller
passes in the job body override it key by key.

### CDC sources

`/api/v1/cdc/sources` registers Debezium connectors. `ODF_DEBEZIUM_URL` points
at Kafka Connect. Connector names are `odf-p<project>-<slug>`, so two projects
cannot collide, and the database password is stored encrypted and never
returned by the API. Pausing, resuming, refreshing status and deleting map onto
the Connect REST API.

### Table maintenance

`POST /api/v1/lakehouse/maintain` runs Iceberg procedures through Trino:

```json
{"datasource_id": 3, "tables": ["events"],
 "optimize": true, "expire_snapshots": true, "retention": "7d"}
```

Each table reports `optimize` and `expire` separately, so one failing table does
not hide the rest. Schedule it from the platform's scheduler or an external cron.

### Catalog durability

Nessie keeps its version store in a PostgreSQL instance that the data plane
creates next to it. `NESSIE_VERSION_STORE=JDBC2` (the default) points Nessie at
`nessie-postgres`; `IN_MEMORY` remains for throwaway environments and loses the
catalog on restart.

Verified: a table written through Trino survives deleting and recreating the
Nessie pod.

### Backup and restore

`scripts/backup_restore_drill.sh` dumps the catalog database, drops a table
through Trino, restores the dump and compares row counts. Iceberg data files are
immutable, so the catalog is the part that needs backing up; the drill leaves
the files in place.

Verified on a table with seven rows: dropped, restored, seven rows again.

### Snapshot cleanup

`expire_snapshots` refuses to run unless the table carries `gc.enabled=true`.
Trino cannot set that property (`ALTER TABLE ... SET PROPERTIES` only accepts
catalog-level properties), so it is set through Spark:

```sql
ALTER TABLE <catalog>.<schema>.<table> SET TBLPROPERTIES ('gc.enabled' = 'true')
```

With Nessie, history is squashed on the main branch, so a table usually has a
single snapshot and expiry has nothing to reclaim. The procedure runs and
returns `ok`; a table with real history would see files removed.

Trino refuses retentions shorter than `TRINO_EXPIRE_MIN_RETENTION` (7 days by
default). Lower it only for a controlled test.

### Known limitation: streaming inserts through the SQL Gateway

A streaming `INSERT` submitted through the SQL Gateway fails with a job-id
resolution error (`Cannot resolve path parameter (jobid) from value "None"`), so
the detached path of the `flink_sql` node and a savepoint against a gateway job
cannot be exercised in this deployment. Queries, DDL and bounded statements work.
Streaming jobs are expected to run as operator-managed Flink deployments until
this is resolved.
