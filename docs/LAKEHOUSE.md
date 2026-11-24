# Lakehouse table management

The Lakehouse page manages Apache Iceberg tables on a Trino datasource. It
uses Iceberg metadata tables and Trino maintenance procedures; it does not
introduce another table catalog.

## Table inspection

Select a Trino datasource and optionally a schema. The page lists tables and
their column counts. Each table exposes:

- **Health**: file count and size, small-file count, snapshot count, partition
  count and issues. More than half small files, too many snapshots or a
  skewed partition produces a warning.
- **Snapshots**: `$snapshots` metadata with snapshot id, committed time,
  operation and summary.
- **Time travel**: query a snapshot id or timestamp with
  `FOR VERSION AS OF` / `FOR TIMESTAMP AS OF`.
- **Maintain**: run `optimize` and `expire_snapshots` through Trino.
- **Schedule**: create a cron maintenance schedule.

## Maintenance

Immediate maintenance accepts:

- optimize small files with a size threshold such as `128MB`
- expire snapshots with a retention such as `7d`
- a table list, or blank for the whole schema

Scheduled maintenance stores datasource, schema, optional table, cron,
retention, threshold and both switches. The scheduler enqueues a
`lakehouse_maintenance` job; the worker runs the same Trino procedures and
writes the result to the job. Failures raise a workspace alert and are
recorded on the schedule.

Run a schedule immediately from the schedule list. Deleting a schedule leaves
the table untouched.

## Permissions

Reading health, snapshots, files and time travel requires a signed-in user in
the project. Running maintenance and changing schedules requires the editor
role. Every action is project-scoped through the datasource.

## Limits

- The page is for Trino-backed Iceberg tables; other datasources are rejected.
- Metadata listings are bounded (up to 2000 rows) and large tables may report
  a listing-limit warning.
- Orphan-file removal is not exposed because the installed Trino version does
  not provide that procedure; use a Spark maintenance job if needed.
