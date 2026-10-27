# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-10-27

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
