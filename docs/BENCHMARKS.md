# Benchmarks

These results come from the reproducible harness in [`bench/`](../bench/README.md).
They are a capacity baseline for a single test host, not a promise for every
deployment. The harness creates an isolated PostgreSQL cluster and removes it
afterwards; it never points at a production control database.

## Test shape

| Item | Value |
| --- | --- |
| Host class | 48-core Linux test host, 125GB RAM |
| Database | PostgreSQL 14.5, isolated cluster |
| Data | 30GB: 1.5M customers, 400k products, 15M orders, 50M order items, 15M payments, 1.5M refunds, 30M events |
| Rows | 113.4 million |
| Sources | PostgreSQL ×2, SQLite, Parquet/CSV files, mock HTTP |
| Tenants | 10 projects, 51 users, 150 assets, 100 quality rules |

## Pipelines

Two published pipelines moved 15M rows each into a PostgreSQL sink:

| Run | Result |
| --- | --- |
| Pipeline 1 | success, 636s (≈23.6k rows/s) |
| Pipeline 2 | success, 668s |

The sink uses batched `executemany`; the earlier row-at-a-time implementation
needed nearly two hours for the same load.

## Load phases

| Phase | Requests | Errors | p50 | p95 | p99 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Warm-up, 10 VU | 241,776 | 0 | 35ms | 49ms | 128ms |
| Baseline, 50 VU | 692,574 | 0 | 192ms | 221ms | 303ms |
| Peak, 100 VU, 60-connection pool | 12,125 | 11,999 | 30s | 30s | 30s |
| Peak retest, 100 VU, 140-connection pool | 156,394 | 0 | 380ms | 434ms | 475ms |
| Fault phase, 60 VU | 646,077 | 360 | 230ms | 265ms | 350ms |
| Soak, 50 VU | 926,536 | 0 | 191ms | 220ms | 307ms |

The 100-VU default-pool cliff is real: a 60-connection pool is not enough for
100 concurrent requests. The retest with 140 connections is a tuning result,
not a recommendation to exceed PostgreSQL's connection budget; use PgBouncer
or more API replicas instead.

## Real query path

Metadata/list traffic is cheaper than dataset/metric/dashboard execution. A
second driver exercises dataset preview, metric query, dashboard data, catalog
search and MCP tools.

| Scenario | Requests | Errors | p95 |
| --- | ---: | ---: | ---: |
| 20 VU, no query cache | 7,839 | 0 | 2,526ms |
| 50 VU, no query cache | aborted by runtime guard at load 53 | — | 3,837ms |
| 50 VU, metric cache (60s) | 100,788 | 0 | 945ms |
| 50 VU, metric + preview + dashboard cache (60s) | 191,678 | 0 | 474ms |

With all three caches enabled, the per-endpoint p95 in the mixed phase was:

| Endpoint | p95 |
| --- | ---: |
| Dataset preview | 494ms |
| Metric query | 516ms |
| Dashboard data | 459ms |
| Catalog search | 397ms |
| Dataset list | 396ms |
| MCP tools | 397ms |

The caches are off by default (`ODF_METRIC_CACHE_TTL_S`,
`ODF_PREVIEW_CACHE_TTL_S`, `ODF_DASHBOARD_CACHE_TTL_S` = `0`) and are
process-local. Choose a TTL that matches the freshness expected by the
business; 15–30 seconds is a reasonable dashboard starting point.

## Recovery checks

- **Worker killed mid-batch:** a 15M-row upsert pipeline recovered in 903s with
  `attempts=1`, a heartbeat-timeout error record and exactly 15,000,000 sink
  rows. No duplicate rows were observed.
- **Tied cursors:** 1,000 source rows across 10 identical `updated_at` groups
  were replayed twice; both runs succeeded and the target retained 1,000 rows.
- **Fault injection:** 200ms business-database latency, worker restart, HTTP
  500 responses and a scheduler stop/start were exercised; the fault phase
  error rate was 0.056%.

## Limitations

- Single test host; multi-replica cache sharing and real HA failover are not
  covered here.
- MySQL, ClickHouse, Oracle and SQL Server were not part of this matrix run.
- The benchmark is infrastructure-heavy; run it on a disposable host and use
  the cleanup step.
