# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

Versioning restarts at 1.1.0 with this release. Earlier public tags were
retired during the reset; the git history remains available.

## [1.1.0] - 2026-11-27

### Platform

- Unified asset catalogue for datasets, metrics, models, pipelines, APIs,
  dashboards, apps and data products, with versions, approval publishing,
  lineage, ownership, certification and lifecycle notes.
- Project-scoped console with role-aware navigation for administrators,
  editors, approvers and viewers; platform administration separated from
  workspace operations.
- Durable PostgreSQL job queue, retrying workers, leader-elected scheduler,
  dependency-aware scheduling, run priority, duration SLAs, cost attribution,
  dead-letter replay, retention and archive.

### Data integration

- Connector registry covering relational databases, openGauss, KingbaseES,
  GaussDB, Dameng DM, ClickHouse, Trino, DuckDB, Hive/Spark Thrift, S3/MinIO,
  files, HTTP, Elasticsearch, MongoDB, Kafka and Airbyte-protocol sources.
- Visual pipeline studio with source, transform, quality, Spark, Flink SQL and
  sink nodes; validation, preview, versioned publish, backfill, cursors and
  templates.
- Quick sync, datasource health history, metadata sync, schema-drift alerts,
  datasource rate and concurrency limits, and encrypted connection settings.

### Lakehouse and engines

- Trino/Iceberg datasource with table health, snapshots, exact snapshot time
  travel, file optimisation, snapshot expiry and scheduled maintenance.
- Spark applications through the Spark Operator and Flink SQL through the SQL
  Gateway, with submit, inspect, cancel and savepoint operations.
- Debezium CDC sources for PostgreSQL, MySQL and Oracle, generated CDC
  pipelines, schema evolution and delete handling.
- DuckDB quality rules now run through the unified SQL query layer, compatible
  with current `duckdb-engine` releases.

### Modelling and analytics

- Visual and SQL datasets, expression metrics, time grains and period
  comparison, transform models with refs and materialisations, tests and
  warehouse layers, column lineage and model-run history.
- Dashboards with cards, charts, tables, maps and text; filters, drill-through,
  GeoJSON maps, scheduled CSV reports, share links and embed snippets.
- Metric catalogue with owners, definitions, usage and dataset links.

### Applications and products

- Multi-page low-code apps with parameters, bindings, actions, page roles,
  component styles, conditional highlights, containers, tabs, modals, uploads,
  approval queues and lists.
- Built-in application templates and a template marketplace.
- Data products with owner, SLA, terms and member assets; packaging and bundle
  export; cost attribution and usage in one view.

### Governance

- Column classification and masking, row policies, governed SQL restrictions,
  data standards and column mapping, glossary and domains.
- Data contracts with freshness and quality checks, contract check history and
  enforcement.
- Quality rules for freshness, nulls, uniqueness, range, accepted values,
  regex, schema, drift and custom SQL; pass rates, SLA alerts and daily trends.
- External metadata import for dbt and BI metadata; read-only external datasets
  in the physical catalog.
- Approval-gated writes, audit trails, asset grants, requests and public share
  modes that strip write components.

### Administration

- Users, platform roles, projects, quotas, sign-in policy, OIDC/LDAP, branding,
  announcements, feature flags, engine, CDC, Airbyte and lineage settings.
- Backup export, restore guidance, audit filters and CSV export, retention
  policies and system checks.
- Management API, signed public gateway, GraphQL gateway, streamable HTTP MCP
  server and stdio MCP entry point with approval-protected write tools.

### Fixed

- Iceberg snapshot identifiers are returned as strings so time travel keeps
  full 19-digit IDs instead of JavaScript-rounded numbers.
- The desktop application editor no longer auto-stacks components when the
  canvas host is narrow; stacking applies only to tablet preview.
- Choosing a datasource in the pipeline node editor clears the table/topic
  field before the metadata lookup and ignores stale responses, so a topic
  typed immediately after selection is preserved.
