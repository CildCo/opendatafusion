# Architecture

OpenDataFusion is split into four independently deployable processes. The API
is stateless; scheduling and execution are durable and can be scaled
separately.

```
                 ┌──────────────────────────────┐
                 │  nginx / reverse proxy       │
                 └──────────────┬───────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐      ┌─────────────────┐     ┌─────────────────┐
│ odf-api       │      │ odf-mcp         │     │ static SPA      │
│ FastAPI       │      │ streamable HTTP │     │ Vue 3           │
│ stateless     │      │ :18082          │     │ /ui/            │
└───────┬───────┘      └────────┬────────┘     └─────────────────┘
        │                       │
        └───────────┬───────────┘
                    ▼
          ┌──────────────────┐
          │ PostgreSQL       │
          │ control + jobs   │
          └───────┬──────────┘
                  │
        ┌─────────┴──────────┐
        ▼                    ▼
┌───────────────┐    ┌─────────────────┐
│ odf-scheduler │    │ odf-worker × N  │
│ leader lock   │    │ SKIP LOCKED     │
│ enqueues jobs │    │ executes flows  │
└───────────────┘    └─────────────────┘
```

## Components

| Process | Responsibility | Scale |
|---|---|---|
| `odf-api` | Management API, auth, metadata, interfaces, health, audit | Horizontal, stateless |
| `odf-mcp` | MCP tool server for external AI operators | Horizontal, stateless |
| `odf-scheduler` | Cron evaluation, enqueue due flows | One leader (PG advisory lock) |
| `odf-worker` | Claim jobs, execute ETL connectors, heartbeat | Horizontal |
| PostgreSQL | Source of truth, durable job queue | Primary/standby |
| Static SPA | Vue 3 admin console | Any static server |

## Execution semantics

- **Durable queue**: `POST /flows/{id}/runs` only inserts a `job` row. It never
  executes ETL in the request thread.
- **At-least-once**: a worker claims a job with `FOR UPDATE SKIP LOCKED`, runs
  the flow, and marks it `success` or retries with backoff. Sinks use primary
  key upserts, so replay is idempotent.
- **Heartbeat and recovery**: a running job updates `heartbeat_at`. Jobs whose
  heartbeat is older than the timeout are requeued and counted as attempts.
- **Bounded retries**: `max_attempts` (default 3) then `failed`, with
  `last_error` persisted.
- **Scheduler leader**: the scheduler holds `pg_try_advisory_lock(999999)`; a
  second scheduler exits instead of double-enqueuing.
- **Cursor safety**: the flow cursor advances only after the sink write
  transaction commits. A failed run leaves the cursor unchanged.
- **Tie-safe cursor**: the cursor is `(cursor_column, pk)`, so rows sharing a
  timestamp are not skipped at batch boundaries.
- **Drain per run**: a pipeline job processes up to 100 batches and stops when
  every cursor source is exhausted. Each batch commits its own cursor, so a
  later failure resumes from the last successful batch. A source without a
  cursor column is read once per run; backfill remains the explicit path for
  replaying a fixed range.

## Scaling

- API: run 2+ replicas behind nginx; JWT is stateless and the shared
  PostgreSQL holds all state.
- Workers: run N replicas; `SKIP LOCKED` distributes jobs without coordination.
- Scheduler: run one leader plus hot standbys; a standby exits and can be
  restarted to take over after the leader dies.
- Database: use PgBouncer in front of PostgreSQL. Partition `flow_run`,
  `audit_log`, and `job` by time when volume grows.
- Queue: PostgreSQL `SKIP LOCKED` is sufficient for moderate throughput. Move
  to RabbitMQ/Kafka when job rate or retention requires it; the `job` table is
  a transactional outbox that can feed a broker.

## Security

- JWT for management APIs; roles: viewer, editor, approver, admin.
- AK/SK HMAC-SHA256 for the public OpenAPI (SHA1 can be disabled), with a `Date` window and
  constant-time comparison.
- Approval tokens are HMAC-signed, target-bound, and time-limited.
- Datasource passwords and SK values are Fernet-encrypted at rest and never
  returned by list APIs.
- MCP read tools are unauthenticated at the process level; deploy the port
  behind a firewall or a reverse proxy with auth.

## Failure model

| Failure | Behaviour |
|---|---|
| API dies | No in-flight ETL is lost; jobs continue in workers. |
| Worker dies | Heartbeat times out; job is requeued and retried. |
| Scheduler dies | Standby can acquire the leader lock; missed runs are enqueued on recovery. |
| Database unavailable | API returns errors; workers retry claims; no data loss beyond in-flight batches. |
| Sink write fails | Target transaction rolls back; cursor stays; job retries. |
| Source unavailable | Run fails, `err_num` is set, job retries/fails visibly. |

## Pipeline Studio

- **Asset model**: `asset` + `asset_version` with draft/published/archived
  versions; publish is approval-gated and immutable; rollback creates a new
  version from an old one.
- **Canvas**: Vue Flow, nodes `source` / `filter` / `select` / `rename` /
  `cast` / `join` / `aggregate` / `union` / `dedupe` / `quality` / `sink`.
  `join`/`union` take two inputs via `left`/`right` edge ports.
- **Schema**: propagated node by node; source types come from synced metadata
  or live inspection. `/validate` reports schema errors.
- **Error policy**: `on_error` is `fail` (default), `skip` or `quarantine`;
  a skipped node records a failed node run and passes its first input
  downstream.
- **Lineage**: publishing writes idempotent table→asset and asset→table
  edges, plus column-level table→table edges derived through select, rename,
  cast, join, union and aggregate transforms. The catalog API returns both.
- **Preview**: `POST /api/v1/pipelines/{id}/preview` runs the selected node
  and its ancestors through the same executor used by production, with the
  unsaved canvas content, a 1000-row / 30-second / 512 MB sandbox, and
  external file access disabled; sinks are skipped.
- **Execution**: topological order; source/sink reuse the connector layer;
  transformations run in DuckDB over Arrow tables with quoted identifiers and
  schema-checked columns. Per-node rows/ms/errors are stored in
  `pipeline_node_run`.
- **File sources**: a `file` datasource points at one local CSV/TSV, Parquet,
  JSON or Excel file. Each query materializes it into an in-memory DuckDB
  `file` schema, then disables external file access so SQL cannot read other
  server files. Metadata sync records the generated table and schema drift
  raises an open `schema drift: schema.table` alert.
- **Extended connectors**: Oracle uses `oracledb` thin mode
  (`oracle+oracledb`), SQL Server uses `pymssql` (`mssql+pymssql`), and both
  sync only the connection's default schema. ClickHouse uses
  `clickhouse-connect` over HTTP(S); its metadata, read paths and ETL source
  are implemented directly, and a ClickHouse sink is intentionally not
  offered because the engines are append-oriented.
- **Cursor**: each source node keeps its incremental cursor in
  `asset.cursor_json`; it is written only after every node (including sinks)
  succeeds, so a failed sink leaves the cursor unchanged.
- **Backfill**: `POST /pipelines/{id}/backfill` enqueues a
  `pipeline_backfill` job. The worker replays the published DAG from an
  explicit start cursor in batches, optionally stopping at an inclusive end
  cursor, and never writes `asset.cursor_json`. Every source needs a cursor
  column; jobs are capped at 1000 batches.
- **Scheduling**: `scheduler_tick` handles connector `flow` schedules and
  published, enabled `pipeline` assets; cron is editable from the Studio.
  Drafts are never scheduled.
- **Sink modes**: `upsert` (composite primary key) and `append`.
- **Approval**: publish / rollback / pause / resume are change requests with
  target-bound approval tokens and audit records.
- **Access control**: every pipeline route is scoped to the token's project;
  create/draft/run require the editor role, publish/rollback require the
  approver role.

## API Studio

- API definitions are `asset(type="api")` + immutable `asset_version`
  records; drafts never serve traffic.
- Visual mode compiles a single-table query to bound SQL; SQL mode is
  read-only guarded. Identifiers are quoted and validated against table
  metadata.
- Preview uses the draft or unsaved content; management test and the
  public gateway use the published version of an enabled asset.
- Simple interface records (`data_interface`) remain available as a
  lightweight SQL endpoint registry. The gateway resolves a versioned API
  asset first, then uses the matching interface record when no asset owns the
  key.

## Model Studio

- Dataset assets reuse the visual API query compiler; metrics query the
  published dataset version and compile a grouped aggregate.
- Both use the shared asset/version model, project checks, approval tokens and
  audit.
- MCP exposes `dataset_schema` and `query_metric` as read tools.

## Dashboard Studio

- Dashboards are `asset(type="dashboard")` with a 12-column widget grid;
  widgets query published metrics/datasets and isolate errors per widget.
- Dashboards may declare typed parameters; widgets bind filters to them and
  chart/table clicks can set a declared parameter (`emit`).
- Widget filters are validated against model output and resolved to bound
  literal filters before execution; dataset and metric queries share the
  read-only compiler.
- The editor supports drag/resize, ECharts rendering, validation, versioned
  publish/rollback, a read-only `/dashboards/{id}/run` page and an MCP
  `dashboard_data` read tool that accepts parameters.

## App Studio

- Apps are `asset(type="app")`; content holds ordered pages with typed page
  parameters and `text` / `metric` / `table` components.
- Components query published datasets/metrics only. Dataset page parameters
  are passed into the read-only query compiler; each component executes
  independently and reports its own error.
- The shared runtime renders the filter bar, metric cards, tables and a
  row-detail drawer in both the draft editor and `/apps/{id}/run`.
- Forms insert, update or delete rows through the published dataset's
  datasource: physical columns are whitelisted, identifiers quoted, values
  bound, and update/delete must affect exactly one row.
- Optional `allow_roles` restricts submission; the role is resolved from
  the authenticated user server-side.
- Submissions are authenticated, project-scoped and audited without values;
  SQL errors are reduced to a generic failure.
- Publish/rollback use approval tokens; MCP exposes `app_data` for published
  pages (no AI write tool).

## SQL Workbench and federation

- `odf.workbench` runs read-only SQL with the shared SQL guard, project-scoped
  datasources, statement timeouts and audit (hash/preview only).
- Federation snapshots up to four tables (20k rows each) into Arrow, registers
  them as aliases in in-memory DuckDB, disables external access, blocks
  file/extension primitives, and runs one read-only query.
- MySQL/MariaDB DSNs normalize to PyMySQL; read sessions enable ANSI quotes so
  the shared identifier compiler works, and pipeline sinks support
  `ON DUPLICATE KEY UPDATE`.

## Ops Center

- `odf.ops` aggregates queue counts, failed jobs, alerts, flow health and a
  merged alert/health timeline from existing tables; no new schema.
- Jobs are project-scoped through their flow or asset; only failed jobs can
  be retried, which clears attempts/locks and writes audit.
- Alerts and health endpoints derive the project from the token; audit
  search is admin-only because the global log has no project column.
- MCP exposes `ops_summary`, `list_jobs` and `list_alerts` read tools plus
  editor-gated `retry_job` and `ack_alert`.

## Production hardening

- Authentication: password policy, refresh, TOTP (stdlib), OIDC code+PKCE
  and optional LDAP; per-project member roles override global roles.
- Menu permissions are enforced for non-admins via `allowed_menus`; dataset
  row policies are appended as bound filters to dataset/metric reads.
- API gateway enforces AK/API CIDR allowlists, DB-backed fixed-window rate
  limits, and records per-day call statistics.
- `/metrics` exposes HTTP/job/webhook/API counters; request IDs and optional
  JSON logs; `scripts/backup.sh`/`restore.sh` and `docs/HA.md`.
- `python -m odf.cli rotate-fernet|rotate-aksk|rotate-webhook-secret`
  re-encrypts/rotates secrets.

## Ecosystem modules

- Webhooks use a durable `webhook_delivery` outbox drained by the scheduler
  leader; payloads are signed with HMAC-SHA256, redirects are disabled and
  private/loopback targets require an explicit setting.
- Files are stored under `ODF_FILE_DIR` by SHA-256, one row per upload,
  with blob deletion only when no row references it.
- Portal settings are project-scoped branding/menu visibility; Vue applies
  the brand, CSS primary color and hides menu paths.

## Projects and API grants

- `interface_grant` / `interface_request` model cross-project API access;
  requests are owner-approved, grants are revocable, and the gateway allows
  owner calls or active grants only.
- `/projects/mine` and `/auth/switch-project` issue a fresh project-scoped
  token after membership validation; the header selector reloads the app.
- The API catalog exposes published API names/keys/owner only.

## Share links

- `share_link` stores SHA-256 token hashes, asset/project, expiry and
  revocation; raw tokens are returned once and sent via `X-Share-Token`.
- Public routes render published app/dashboard content only; app forms are
  stripped server-side and there is no public write path.
- Token expiry/revocation is checked on every request; editors create and
  revoke links with audit.

## AI tool layer

- External agents use MCP or `POST /api/v1/mcp/{tool}`; there is no built-in
  chat UI.
- Read tools cover assets, pipeline schemas, node preview, runs, diagnosis,
  API tests, lineage and the platform snapshot.
- Draft tools create/update assets; publish/rollback/run/pause/resume/revoke
  require an approval token bound to `(target, action)`.
- `submit_app_form` requires an approval token bound to
  `(asset, "app_form_submit")`; it executes the published form as an
  approved action and never accepts client-supplied form definitions.
- Every call writes an audit record with actor `mcp`; approval tokens are
  never logged.

## What is intentionally simple in this release

- Single-region deployment.
- PostgreSQL as the only queue; no external broker required.
- Synchronous connector calls with per-request timeouts.
- No multi-tenant row-level isolation beyond project-scoped API checks.
