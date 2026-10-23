# Roadmap

This roadmap communicates direction, not a delivery commitment. Priorities are
reviewed with the community each release.

## Near term

- Shared query cache across API replicas (Redis or an equivalent backend).
- Dashboard widget pre-aggregation and freshness policies.
- PgBouncer and read-replica guidance for higher concurrency.
- Log-based CDC connectors in addition to cursor-based incremental sync.
- More live integration fixtures for ClickHouse, Oracle and SQL Server.

## Mid term

- Multi-replica HA drills with automated failover checks.
- Data contracts and freshness SLAs attached to published assets.
- Richer catalog ownership, stewardship and approval workflows.
- A versioned documentation site generated from `docs/`.

## Non-goals

- A built-in chat interface. The product exposes MCP and HTTP surfaces for
  external operators instead.
- A general-purpose compute engine or a lakehouse. Pipelines are intended for
  operational data delivery, not arbitrary distributed compute.
- Silent, unreviewed publishing. Approval and audit are part of the product
  model.
