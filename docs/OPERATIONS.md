# Operations

## Data retention

The scheduler runs a retention pass once per day. Each class has its own
window; `0` disables a class.

| Setting | Default | Removed when |
| --- | --- | --- |
| `ODF_RETENTION_QUERY_RUN_DAYS` | 30 | older than the window |
| `ODF_RETENTION_JOB_DAYS` | 90 | terminal status and older |
| `ODF_RETENTION_NOTIFICATION_DAYS` | 30 | older than the window |
| `ODF_RETENTION_ALERT_DAYS` | 180 | closed and older |
| `ODF_RETENTION_WEBHOOK_DELIVERY_DAYS` | 30 | delivered or failed and older |
| `ODF_RETENTION_CONTRACT_CHECK_DAYS` | 90 | older than the window |

- Platform console → Administration → Operations shows the window, eligible
  rows and a **Prune now** action.
- CLI: `python -m odf.cli prune-data` (dry run) and `--apply`; override with
  `--days job=60 --days query_run=14`.
- Removing jobs also removes their pipeline node runs; removing notifications
  removes their read receipts.
- Audit retention stays separate (`prune-audit`).

## Dead letters and replay

Failed jobs are listed in **Operations → Dead letters**. Filter by asset type,
select up to 100 and replay. Replay resets attempts, clears the last error and
requeues the job; a second replay is skipped while the target already has a
queued or running job. Every replay is audited.

## Datasource limits

Datasources can carry two limits, configured from the datasource row:

- **Queries per minute** applies to the workbench, execution plans, model
  preview and federated queries. Over-limit requests return HTTP 429.
- **Concurrent jobs** applies to model and lakehouse maintenance jobs. A job
  that finds no slot waits 30 seconds and retries; after about one hour it
  fails with `datasource concurrency limit reached`.

Both default to `0` (unlimited). The dialog shows current usage.

## System check

`python -m odf.cli doctor` prints database reachability, current and head
migration revisions, asset/job counts, open alerts, query history size and
disk headroom. It exits non-zero when the database is unreachable, migrations
are pending or free disk is below 512 MB. The same report is available in
Administration → Operations.

`python -m odf.cli backup-check --path <file>` verifies that a backup file
exists, is non-empty and is readable: plain SQL dumps must contain CREATE TABLE
or COPY statements, gzip files must decompress, and tar.gz archives must list
entries.

## HA smoke test

```bash
python scripts/ha_smoke.py --url http://api-1:18080 \
  --url http://api-2:18080 --url http://api-3:18080
```

Every replica must answer `/livez` and `/readyz`. Run it after scaling the API,
changing the load balancer or failing over the scheduler. The scheduler uses
the PostgreSQL advisory lock `999999`; only one leader runs.
