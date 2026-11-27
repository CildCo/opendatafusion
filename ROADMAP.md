# Roadmap

This roadmap communicates direction, not a delivery commitment. Priorities are
reviewed with the community each release.

## Near term

- Shared query cache across API replicas (Redis or an equivalent backend).
- Dashboard widget pre-aggregation and data freshness policies.
- PgBouncer and read-replica guidance for higher concurrency.
- More live integration fixtures for ClickHouse, Oracle, SQL Server and DM.
- A versioned documentation site generated from `docs/`.
- Richer connector certification and capability reporting in the console.

## Mid term

- SAML and SCIM for enterprise identity, alongside the existing OIDC/LDAP paths.
- External KMS-backed encryption for datasource secrets and backups.
- Multi-replica HA drills with automated failover verification.
- Cross-project data-product discovery and request workflows.
- A connector marketplace with signed packages and upgrade guidance.
- Evaluation and tracing hooks for external agents using the MCP surface.

## Non-goals

- A built-in chat interface. The product exposes MCP and HTTP surfaces for
  external operators instead.
- A storage engine or distributed compute engine. Lakehouse tables and Spark or
  Flink execution are managed through Trino, Spark and Flink rather than
  reimplemented in the control plane.
- Silent, unreviewed publishing. Approval and audit are part of the product
  model.
