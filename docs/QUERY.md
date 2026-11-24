# Query workbench and performance

The workbench runs read-only SQL against any query-capable datasource and
records every run so that slow and failing statements can be reviewed

## Running queries

- Single-source queries run against one datasource with a row limit.
- Federated queries materialize up to four tables into DuckDB and query them
  together; each source is capped at 20,000 rows.
- Results can be exported as CSV.
- **Execution plan** runs `EXPLAIN` for the current statement on SQL,
  Trino, Hive, ClickHouse and DM datasources and shows the plan rows.
- Datasources with column-level policies are read-only in the workbench for
  non-admins; queries against them are rejected.

## Query history

Every executed statement is recorded with:

- actor, datasource, source (`workbench`, `federated` or `model`)
- status, duration in milliseconds and returned rows
- a SHA-256 hash, the first 200 characters and the full text (up to 20,000
  characters) for reopening
- the error message when the statement fails

Open **History** in the workbench to list the latest 50 runs. Select a run to
reload its SQL into the editor. Federated runs cannot be reloaded because
they have no single datasource.

## Performance view

The operations centre has a **Query performance** tab for the last 7 or 30
days:

- total, failed, average, P50 and P95 duration
- counts, failures and average duration by source and by datasource
- the ten slowest statements with SQL preview, user and time

The view covers workbench, federated and model-preview queries. Pipeline and
model job durations remain in the job history.

## Limits

- Query text is stored in the control database; treat it as sensitive.
- Percentiles are computed over at most 20,000 recent runs per window.
- History is not pruned automatically; archive or trim `query_run` according
  to your retention policy.
