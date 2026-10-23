# Observability and performance

## Metrics

`GET /metrics` exposes Prometheus text format (disable with
`ODF_METRICS_ENABLED=false`):

- `odf_requests_total{method,path,status}` — path is the route template, not
  the raw URL, so IDs do not explode cardinality.
- `odf_request_duration_seconds` histogram with standard buckets.
- `odf_queue_depth{status}` — durable job states.
- `odf_webhook_pending`, `odf_alerts_open`.
- `odf_db_pool_size`, `odf_db_pool_checked_out`, `odf_db_pool_overflow`.
- `odf_uptime_seconds`, `odf_build_info`, `odf_otel_enabled`.
- `odf_query_cache_hits{kind}`, `odf_query_cache_misses{kind}`.
- Existing domain counters (`odf_api_calls_total`, `jobs_total`,
  `webhook_deliveries_total`).

`/livez` is a process check; `/readyz` checks PostgreSQL and returns 503 on
failure. Do not scrape `/metrics` through an untrusted edge without network
restrictions.

## Tracing

Set:

```bash
ODF_OTEL_ENABLED=true
ODF_OTEL_ENDPOINT=http://otel-collector:4317
ODF_OTEL_SERVICE_NAME=odf
ODF_OTEL_SAMPLE_RATIO=0.1
```

Install `pip install -e ".[otel]"`. FastAPI, SQLAlchemy and outbound httpx
calls are instrumented. If tracing is enabled without the extra installed, the
API fails fast at startup instead of silently dropping traces.

## Connection pool

The default pool is `20 + 40` connections (`ODF_DB_POOL_SIZE` +
`ODF_DB_MAX_OVERFLOW`). A 30-connection pool (the previous `10 + 20`
default) collapses at 30 concurrent requests: requests queue for the full
`ODF_DB_POOL_TIMEOUT` (30 s) and measured throughput drops from ~200 RPS to
~2.5 RPS. Keep the total pool at least twice the target concurrency, and use
PgBouncer before running many API replicas against one PostgreSQL instance.

A 100-VU run against 30GB of data reproduced the same cliff at the default
`20 + 40` pool: 12,125 requests produced 11,999 30-second timeouts. Raising
the bench pool to `60 + 80` (140 connections) and repeating the 100-VU run
gave 156,394 requests, 0 errors, p95 434 ms and p99 475 ms. Production
PostgreSQL currently allows 100 connections, so reach 100 VUs with
PgBouncer, more API replicas or a lower per-process pool; do not copy the
bench's 140-connection setting blindly.

## Real-data check

On a 48-core PostgreSQL test host, the MIT-licensed `chinese-poetry` corpus was
loaded as 78,657 rows (57,607 Tang poems, 21,050 Song ci; 20.3 MB CSV,
5.85 million Chinese characters). A published pipeline reading PostgreSQL,
filtering `dynasty = '唐'`, and upserting into a second table moved 57,607
rows in 20.1 s (about 2,865 rows/s). A grouped metric over the full corpus
returned the correct two dynasty counts in 35 ms.

## Load test

A dependency-free async load tester is included:

```bash
python scripts/loadtest.py --base http://127.0.0.1:18080 \
  --username admin --password '...' --project 1 \
  --path /api/v1/health/snapshot --requests 1000 --concurrency 50
```

It reports status counts, RPS, p50/p95/p99 and max latency. Run it against a
staging copy, not production, and capture `/metrics` and PostgreSQL
`pg_stat_statements` during the run.

Suggested gates before a release:

| Scenario | Target |
| --- | --- |
| `GET /livez` / `/readyz` | p99 < 20 ms |
| Authenticated catalog/health reads | p99 < 300 ms at 50 concurrency |
| API gateway query with 100 rows | p99 < 1 s |
| Worker backlog | drains within one scheduling interval |

## HA topology

- N API replicas behind a load balancer using `/readyz`.
- Exactly one scheduler leader; PostgreSQL advisory lock `999999` enforces it.
- N workers; `job` claims use `FOR UPDATE SKIP LOCKED`, so replicas do not
  double-run a job.
- Shared `ODF_FILE_DIR` (NFS) or the S3 backend for multiple API replicas.
- PostgreSQL is the only required shared dependency.

`tests/integration` includes a live advisory-lock check; run it against the
integration PostgreSQL before changing scheduler code.

## Hot indexes

The queue and delivery paths use composite indexes:

- `ix_job_status_run_at (status, run_at)`
- `ix_webhook_delivery_status_next (status, next_attempt_at)`

Add indexes through Alembic only, and validate with `EXPLAIN (ANALYZE,
BUFFERS)` on production-sized data.

## Metric cache

`ODF_METRIC_CACHE_TTL_S` (default `0`, disabled) and
`ODF_METRIC_CACHE_SIZE` (default `256`) add an in-process TTL cache for
metric queries. The key includes the metric asset/version, compiled SQL,
bound parameters, role and row limit, so role-scoped masking and different
parameters do not share entries. It is process-local: API replicas do not
share a cache.

On the 30GB benchmark, enabling a 60-second cache changed a 50-VU real-query
run from "aborted at load 53 with 24 errors / p95 3.8s" to 100,788 requests,
0 errors, p95 945ms and p99 1,083ms, with host load around 12-15. Dataset
preview (955ms) and dashboard data (1,035ms, p99 2.85s) remain above the
500ms target. Keep the cache disabled until the business accepts the chosen
freshness window; 15-30 seconds is a reasonable starting point for dashboards.

### Full query cache result

Adding preview and dashboard caches on top of the metric cache changed the
same 50-VU, 30GB real-query run from 100,788 requests / p95 945 ms to
191,678 requests / 0 errors / p95 474 ms / p99 561 ms. By endpoint in the
mixed phase: dataset preview 494 ms, metric 516 ms, dashboard 459 ms,
catalog 397 ms, list 396 ms. Host load stayed around 12-15. All caches are
off by default and process-local; use a deliberate TTL (15-30 seconds is a
reasonable starting point) and do not assume they are shared across API
replicas.
