# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

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
