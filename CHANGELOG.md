# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [2.6.0] - 2026-11-25

### Added

- Cross-project asset sharing for published APIs, datasets and models:
  requests by asset id or key, approval, grants, revocation and a shared-asset
  list. Datasets open a masked published preview; models expose layer,
  materialization, target and declared columns without SQL; APIs keep the
  AK/SK gateway path.
- Quality SLA: rules store `sla_percent`, the list flags rules below SLA, and
  results show a 30-day daily pass/fail table and the current failure streak.
- `partition` incremental strategy for Trino: replaces the partitions present
  in the source instead of merging row by row, with a 10,000-partition cap and
  full-rebuild fallback.
- CDC sink type validation: values that cannot be coerced to the target
  column type fail the run with a curated column error.

### Changed

- `interface_grant` and `interface_request` become `asset_grant` and
  `asset_request` with `asset_type`; existing rows become `api`. Migration
  `e5f6a7b8c9d0`. The previous `/api-*` grant routes remain as API-only
  aliases.
- The console menu item "Access control" is renamed "Asset sharing".

## [2.5.0] - 2026-11-25

### Added

- Data retention: the scheduler daily prunes terminal jobs, query history,
  notifications, closed alerts, webhook deliveries and contract checks by
  per-class windows; `odf prune-data` supports dry runs and overrides, and the
  platform console shows counts and a manual prune action.
- Dead letters: final failed jobs are listed separately, filtered by asset
  type and replayed in batches of up to 100 through the normal queue.
- Datasource limits: per-datasource queries-per-minute for interactive SQL and
  concurrent model/lakehouse jobs; over-limit queries return HTTP 429 and
  blocked jobs wait and retry.
- `odf doctor` reports database reachability, migration revision, counts and
  disk headroom; the platform console shows the same report.
- `odf backup-check` validates SQL, gzip and tar.gz backups.
- `scripts/ha_smoke.py` checks `/livez` and `/readyz` on every API replica.
- Scheduled data contracts: a six-field cron queues contract jobs through the
  normal queue, stores results and history, and fails the job on drift.
- Classification propagation: model publishing copies column policies from
  its source table or parent models to the physical target, without
  overwriting manual policies.
- CDC schema evolution: the `cdc` sink mode can add new source columns with an
  inferred type before writing; generated CDC pipelines enable it.
- Native `MERGE INTO` for Trino/Iceberg incremental models when source and
  target columns match, with the portable path as fallback.

### Changed

- Contract checks and datasource limits add columns and tables:
  migrations `b2c3d4e5f6a7` and `c3d4e5f6a7b8`.

## [2.4.0] - 2026-11-24

### Added

- Table materialization builds a shadow table, runs the model tests against
  it and swaps it into place only when every test passes. A failing test drops
  the shadow and leaves the previous table intact.
- **Infer from SQL** parses model SQL with `sqlglot` and fills column sources
  for direct projections, single-column expressions and joins, without
  overwriting manual sources.
- Data contracts gain freshness checks: a time column and maximum age are
  validated against the live table, reporting stale, empty or non-time data.
- Query performance adds normalized statement templates and a per-user
  breakdown.
- CDC delete propagation: the source node emits `payload.before` rows with
  `__odf_op = delete` when **Propagate deletes** is enabled, and the new `cdc`
  sink mode deletes by primary key and upserts the rest.

### Changed

- Generated CDC pipelines use `cdc` source and sink settings.
- Table materialization no longer drops the target before running tests.

### Dependencies

- Added `sqlglot`.

## [2.3.0] - 2026-11-24

### Added

- Query history: every workbench, federated and model-preview query is
  recorded with status, duration, rows, error and reopenable SQL.
- Query performance tab in the operations centre with total, failure, average,
  P50 and P95 duration, breakdowns by source and datasource, and the ten
  slowest statements.
- Workbench execution plans through `EXPLAIN` for SQL, Trino, Hive,
  ClickHouse and DM datasources.
- Transform model partitioning for Trino / Iceberg tables, with up to four
  partition columns.
- `merge` incremental strategy: rows for the selected keys are replaced, so
  source updates and deletes reach the target. Above 50,000 keys the model
  rebuilds the table instead.
- Model column definitions with source mapping, surfaced as column-level
  lineage in the lineage drawer and catalog.
- Data contracts for datasets and models: generate from the live table,
  check structure and types, optionally reject extra columns, and enforce the
  contract on model runs.
- Generate CDC pipelines from a Debezium source: one branch per subscribed
  table, Debezium envelope unwrapping and upsert sinks.
- Template gallery for transform models (staging, incremental merge,
  deduplicated mart) and pipelines (table sync by key).

### Changed

- Model unique keys are limited to eight columns and validated as
  identifiers.
- The web console API client supports `PATCH` requests.

### Fixed

- Contract and query-history routes return curated errors and stay
  project-scoped.

## [2.2.1] - 2026-11-24

### Fixed

- Transform model validation, preview and target failures return curated
  messages instead of exception text, clearing a stack-trace-exposure
  finding.

## [2.2.0] - 2026-11-24

### Added

- Transform models: SQL assets with `{{ ref('key') }}` dependencies,
  view/table/incremental materializations, incremental keys, warehouse
  layers, preview, tests, scheduling, approval, rollback and model lineage.
- Model tests (`not_null`, `unique`, `accepted_values`, `relationships` and
  custom SQL) that fail the job, store results and raise alerts.
- Lakehouse table management: table health, snapshots, file and partition
  statistics, time travel by snapshot or timestamp, immediate maintenance and
  cron maintenance schedules with run history and alerts.
- MCP tools for listing, creating, validating, previewing, publishing and
  running transform models.

### Changed

- The scheduler runs published transform models alongside pipelines and
  honours model-to-model dependencies.
- Scheduling dependencies, asset lineage, bundles, the operations queue and
  the console model list include transform models.
- Maintenance jobs carry a project id so they appear in the project
  operations queue.

## [2.1.0] - 2026-11-24

### Added

- Airbyte protocol connectors: import an Airbyte source by image or local
  command, discover its streams, sync their schemas into the catalog and use
  them as pipeline sources. Disabled by default and gated by an image/command
  allowlist, timeout and platform administrator switch.
- OpenLineage events for pipeline and backfill jobs (`START`, `COMPLETE`,
  `FAIL`) with input/output datasets, run facets and error messages.
- Catalog export as JSON (`GET /catalog/export`) and scheduled push to an
  external catalog endpoint, with a manual **Sync now** action.
- A GraphQL gateway at `/openapi/graphql`: signed AK/SK requests, a schema
  built from published APIs, typed arguments, introspection and a console
  schema/example viewer.
- A map dashboard widget with uploaded GeoJSON, metric dimension and value,
  visual scale, tooltips, drill-through and share-page rendering.
- A mobile navigation drawer and responsive editor layouts for dashboards,
  models, APIs and apps.

### Changed

- Airbyte and lineage settings live in platform administration; the console
  can send an OpenLineage test event and push the catalog immediately.
- Pipeline jobs emit lineage only when an endpoint is configured; failures in
  the lineage endpoint never block a job.

## [2.0.0] - 2026-11-24

### Removed

- The legacy integration-flow module: its routes, console pages, worker,
  scheduler hooks, models and health events are gone.
- The legacy SQL-interface module: its routes, console page, gateway fallback
  and models are gone.
- Legacy MCP tools (`list_flows`, `flow_health`, `diagnose_flow`,
  `pause_flow`, `resume_flow`, `get_flow`, `rollback_flow`, `get_interface`,
  `publish_interface`, `revoke_interface`).
- `GET /api/v1/health/snapshot`, `POST /api/v1/flows/*` and
  `/api/v1/interfaces/*` endpoints; old console paths redirect to Pipelines
  and Data APIs.

### Added

- Upgrade migration `d7a8b9c0d1e2` converts every remaining flow into a
  published pipeline (schedule preserved) and every interface into a data API
  (key preserved), or leaves a draft with a notification when conversion
  needs review. It then drops the legacy tables and `job.flow_id`.

### Changed

- Scheduling dependencies accept pipelines only.
- Dashboard counters report pipelines and published APIs; operations health
  now relies on job status and alerts.
- The changes page lists and approves asset changes; it no longer creates
  legacy flow/interface change requests.

## [1.9.0] - 2026-11-24

### Added

- Time grains on metrics: day, week, month, quarter and year buckets for
  PostgreSQL-compatible, MySQL-compatible, SQLite, Oracle/DM, SQL Server,
  ClickHouse, Trino/DuckDB and Hive engines.
- Period comparison on metrics: previous period or the same period last year,
  with `<measure>_previous`, `_delta` and `_delta_pct` columns. Date filters
  move with the comparison window, and dashboards draw a dashed comparison
  series while cards show the change.
- Drill-through from dashboard charts, metric cards and metric tables to the
  underlying dataset rows, respecting metric and widget filters, row policies
  and column masking, with CSV export from the detail drawer.
- Scheduled dashboard reports with a six-field cron, CSV snapshots stored as
  project files, a notification, a `report.ready` webhook event, run history,
  run-now and download from the console.
- An embed snippet in share dialogs for read-only dashboards and apps.

### Changed

- Dashboard and app validation treat a metric's time column as a dimension, so
  time-grain metrics work in charts, pivots, tables and apps without listing
  the column twice.
- Dashboard CSV export and scheduled reports share one renderer.

## [1.8.1] - 2026-11-24

### Fixed

- Metric and SQL-dataset validation now return curated expression and column
  errors instead of raw exception text.

## [1.8.0] - 2026-11-24

### Added

- Environment labels (`dev`, `staging`, `prod`) on projects.
- Project asset bundles: export published assets, datasource names, domains
  and terms as reviewable JSON; validate and import into another project.
  Imports create drafts, remap datasource and asset references, and suffix
  keys that collide across projects.
- Expression metrics: aggregate expressions such as
  `sum(amount) / nullif(count(*), 0)` with a column/function whitelist.
- An external connector SDK: register connector specs and source/sink
  factories from installed modules via `ODF_CONNECTOR_PLUGINS`.

## [1.7.0] - 2026-11-23

### Added

- SQL datasets: define a read-only query over a datasource, derive its
  output columns, and use it as the source for metrics, dashboards and apps.
  This enables multi-table joins inside the semantic layer without a pipeline.
- `count_distinct` metric aggregation.
- Business domains and a glossary, assignable to logical assets and catalog
  tables, with lookup pages in the console.
- Asset contracts (owner, SLA, schema fields, quality commitments, usage
  notes) and a per-asset usage analysis of references, runs, downstream assets
  and API calls.
- A governance drawer in every studio editor and on catalog table details.
- Pivot and area dashboard widgets.

## [1.6.0] - 2026-11-23

### Added

- Server-side pagination and name search for pipelines, datasets, metrics,
  APIs, dashboards, apps, alerts and quality rules.
- A notification centre in the console header, with unread counts and
  read-all, fed by publishing, job failures, alerts and approval requests.
- Draft autosave, navigation guards and optimistic draft-version checks in
  every studio editor, with a conflict prompt instead of silent overwrites.
- A one-click sample delivery path (datasource, pipeline, dataset, metric,
  dashboard and API) from the getting-started checklist.
- Migration actions that turn a legacy flow into a pipeline and a legacy SQL
  interface into an API Studio asset, then disable the old object.
- Job cancellation for queued and running jobs, and a page-level error
  boundary for the console.
- Saved workbench queries and dashboard widget export as CSV.
- Custom-SQL quality rules and row-count anomaly rules with a historical
  baseline, plus an optional alert webhook for external routing.
- A single vocabulary across the console: catalog tables are “数据表”,
  model assets are “逻辑数据集”, and legacy flows/interfaces are marked.

## [1.5.0] - 2026-11-23

### Added

- Datasource health history and optional automatic metadata synchronisation,
  with a health drawer and an auto-sync interval on each datasource.
- A quick-sync dialog that creates a ready-to-run pipeline from a source table
  and a target table.
- Project quotas enforced on assets and jobs, with a usage drawer in the
  administration console.
- Sensitive-column scanning that proposes masking policies and can apply them
  in one step.
- Scheduled quality rules with an alert-on-failure option, and schema-drift
  acceptance from the alert list.
- Full backup export and restore, audit retention, SIEM forwarding, runtime
  and high-availability information, and MCP activity in the platform
  overview.
- SSH jump-host support for SQL connectors through a shared connection helper.
- Asset lineage for datasets, metrics, APIs and dashboards, shown as an
  upstream graph with column-level edges in the studio editors.

### Changed

- All SQL engine creation now goes through one connection service so SSH
  tunnelling, timeouts and driver options behave the same everywhere.

## [1.4.0] - 2026-11-23

### Added

- A separate platform administration console: users and platform roles,
  projects and quotas, sign-in policy with OIDC/LDAP tests, branding and
  announcements, feature flags, engine and CDC defaults, operations and
  platform audit.
- A connector registry with typed forms and capability scopes (test, metadata,
  query, pipeline source/sink). New connectors: S3/MinIO, DuckDB, TiDB,
  Apache Doris, StarRocks, OceanBase, openGauss, KingbaseES, GaussDB, MongoDB,
  Kafka, Hive/Spark Thrift and Dameng DM, bringing the total to 24 types.
- Structured console interactions: JSON trees, result tables, a log viewer,
  diff views, a visual alert-rule builder, a typed property editor, CodeMirror
  SQL editors, draggable pipeline nodes and quick-create actions in the search
  palette.
- Usability work: a command palette, role-aware action visibility, localized
  backend errors, persisted filters and column choices, a virtualized audit
  table and a getting-started checklist.
- Project administrators can manage their own project members; quality actions
  are audited; pipeline runs expose per-node rows, time and error.

### Changed

- Personal settings moved out of the workspace sidebar; platform
  administrators get a fixed administration shortcut.
- The console reads the effective project role so controls match API
  permissions.

### Fixed

- OIDC discovery uses the guarded outbound client; Elasticsearch traffic is
  guarded; connector errors are client-safe.
- Kafka health checks use the admin client signature, and pipeline validation
  skips SQL reflection for pipeline-only connectors.
- Dameng internal `##` tables are excluded from schema sync.

### Security

- The dependency refresh updates Python, frontend and CI tooling floors.

## [1.3.0] - 2026-11-20

### Added

- Dependency-aware scheduling: a downstream flow or pipeline waits for its
  upstream to succeed within a 24-hour window, otherwise a skipped run is
  recorded; cycles are rejected and a page manages the dependencies.
- Dataset profiling: null counts, distinct values and ranges over a bounded
  sample, with ranges hidden for masked columns.
- A metric semantic layer: a metric catalogue with source dataset, definition,
  owner and dashboard/app usage; lineage back to upstream tables; draft and
  published comparison; dataset cross-links; publishing through review; and
  search over definitions, dimensions and consumers.
- MySQL and Oracle change data capture sources alongside PostgreSQL, with a
  connector detail that shows task states and lets subscribed tables be edited.
- Server-side audit filters with CSV export, SQL interface daily usage, and
  alert mute rules that actually suppress matching alerts.
- Flow and SQL interface deletion, and a flow detail route so operations jobs
  open the flow they belong to.
- Change withdrawal by the requester or an approver, bulk deletion on pipelines
  and files, and empty-state create actions across the console.

### Changed

- The sidebar and workspace menu share one definition, and menu permissions
  cover every page.
- Lists show usernames instead of ids, timestamps follow the console language,
  and muted text and glyph-only buttons are easier to read and reach.
- List pagination returns to the first page whenever a filter changes.
- Dialogs and drawers fit narrow screens.

### Fixed

- Flow and SQL interface routes are scoped to the current project, and creating
  in another project is rejected.
- The operations audit tab resolves actor ids to usernames, and alert filters
  offer the error severity used by engine failures.
- Dependency cycle rejections are translated, and change lists resolve the name
  and action of the object they refer to.

## [1.2.0] - 2026-11-19

### Added

- Chinese and English console switch across every page and editor, with
  first-visit browser detection; Element Plus follows the same choice, and
  user guides are published in both languages.
- A dataset detail page in the catalog with overview figures, a masked sample
  preview, columns, quality rules, impact analysis and dataset activity.
- Flow run timing and a run detail with retry, plus downstream impact and a
  version comparison in the flow drawer.
- API call statistics by day and access key on API assets; SQL interfaces show
  the endpoint address and keep a call history.
- CDC connector detail with task states and traces, and subscribed-table
  editing from the console.
- Quality rules show their last result and pass rate and link to the dataset;
  alert rules are managed from the alert console; the operations console links
  jobs and alerts to the objects they belong to.

### Changed

- The console loads each view on demand and splits large libraries into vendor
  chunks, and dates follow the selected console language.

### Fixed

- SQL interfaces use the current project, and their call history no longer
  mixes in publish actions.
- The catalog detail and method console handle projects, history and preview
  limits consistently.

## [1.1.0] - 2026-11-18

### Added

- Trino data sources with connectivity tests, metadata sync and query
  execution, so Iceberg tables behave like any other governed source.
- Engine jobs for Spark (via the Spark Operator) and Flink SQL (via the SQL
  Gateway): submit, list, inspect, cancel and savepoint, with audit records,
  retries and alerts.
- A lakehouse execution profile applied to Spark jobs, so a submission without
  extra configuration reads and writes the project's Iceberg catalog.
- Change data capture sources backed by Debezium, manageable from the API and
  the console.
- `spark` and `flink_sql` pipeline nodes, with lineage from source tables to
  the engine target.
- Lakehouse catalog endpoint and Iceberg table maintenance through Trino.
- Optional namespace-per-project tenancy: namespace, quota, network policy and
  service account created on demand.
- Kubernetes data plane assets: object storage, Iceberg catalog, Trino, Kafka,
  Debezium, Flink, monitoring, ingress and least-privilege identities, plus an
  idempotent installer and an acceptance script.
- Quality rules now run against Trino-backed datasets.
- Flink Kubernetes Operator and cert-manager in the data plane installer,
  with Grafana dashboards for platform health, engine jobs and the lakehouse.
- Console management for project members, API access keys and Iceberg table
  properties; catalog tags can be removed and lakehouse maintenance accepts a
  schema.

### Fixed

- Metadata resync updates datasets in place, so quality rules, tags and
  standard mappings survive a refresh.
- Two-factor setup accepts an empty request body, and the dashboard counts
  published interfaces instead of retired interface records.
- Engine profiles no longer return storage credentials, and gateway failures
  return a fixed message instead of an internal URL.
- Workbench row limiting keeps the outer `ORDER BY`, which SQL Server and
  Oracle reject inside a derived table.

### Changed

- Element Plus runs with the Chinese locale and the bundled assets are rebuilt.
- CI runs the frontend job on Node 24; dependencies and GitHub Actions are
  refreshed, and the integration suite uses the archived Bitnami LDAP image.

### Documentation

- Lakehouse delivery guide, engine profile reference and a 5.1 GB benchmark
  result recorded in `docs/PERFORMANCE.md`.

## [1.0.0] - 2026-10-23

### Added

- API-first low-code data platform with a stateless API, MCP server,
  scheduler and scalable workers.
- Pipeline Studio, API Studio, Model Studio, Dashboard Studio and App Studio.
- Data catalog, column lineage, impact analysis, quality rules, column
  masking, row policies and audit.
- Signed public API gateway, grants, webhooks, files, share links and
  project-scoped RBAC.
- Durable PostgreSQL job queue, cursor-safe backfill, retries, alerts, health
  events, Prometheus metrics and backup/restore tooling.
- Docker Compose, Helm chart and systemd deployment assets.
- Reproducible 30GB benchmark harness and published capacity baseline.
- English and Simplified Chinese documentation.

### Fixed

- Restore editable-install metadata so clean environments can install the
  backend package.
- Install the optional observability and metrics dependencies in CI.
- Use a maintained S3 mock and a reliable ClickHouse readiness check in the
  integration test environment.
- Enforce TLS 1.2 for outbound HTTP and webhook connections, contain local
  storage paths and avoid exposing readiness exception details.

[1.0.0]: https://github.com/CildCo/opendatafusion/releases/tag/v1.0.0
