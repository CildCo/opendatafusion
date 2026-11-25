# Transform models

Transform models are SQL assets that materialize warehouse tables. They reuse
the asset version model, approval flow, job queue, lineage and quality
machinery; there is no separate scheduler or lineage store.

## Model content

```json
{
  "datasource_id": 1,
  "sql": "select city, sum(amount) as total from orders group by city",
  "materialization": "table",
  "schema": "odf_p1",
  "unique_key": [],
  "layer": "staging",
  "description": "",
  "tests": [{"kind": "not_null", "column": "total"}],
  "columns": [],
  "partition_by": [],
  "incremental_strategy": "append"
}
```

- `materialization`: `view`, `table` or `incremental`.
- `layer`: `raw`, `staging`, `intermediate` or `mart`.
- `schema`: blank uses the project schema for Trino, `main` for SQLite and
  DuckDB, `public` for PostgreSQL. MySQL and ClickHouse require an explicit
  schema.
- `unique_key`: used by incremental models to insert only keys that do not
  exist in the target table. Without it, incremental appends every row.
- `incremental_strategy`: `append` (default) or `merge`. Merge requires at
  least one `unique_key` column.
- `partition_by`: up to four columns, Trino / Iceberg tables only. Views
  cannot be partitioned.

## References

Use `{{ ref('model-key') }}` to reference another published model:

```sql
select city, sum(amount) as total
from {{ ref('staging-orders') }}
group by city
```

- The referenced model must be published.
- References form a DAG; cycles are rejected.
- Publishing a model records its refs as scheduling dependencies and lineage
  edges, so downstream models wait for upstream success and the graph shows
  the chain.
- A model cannot reference itself.

## Materialization

- `view` replaces the target view with the compiled SQL.
- `table` builds the result in a shadow table, runs the configured tests
  against it, and only then swaps it into place. A failing test drops the
  shadow and leaves the previous table untouched.
- `incremental` creates the table on the first run and inserts new rows on
  later runs. With `unique_key`, rows whose key already exists are skipped.
  With `incremental_strategy: merge`, existing rows for the selected keys are
  deleted and reinserted, so updates and deletes in the source are reflected.
- On Trino / Iceberg, merge uses a native `MERGE INTO` statement when the
  source and target columns match. Other datasources, or a column mismatch,
  use the portable delete-and-insert path.
- The portable merge runs the model query once to collect keys and once to
  insert. Above 50,000 keys the run rebuilds the table instead, so very large
  merges stay correct at the cost of a full rewrite.
- Partitioning is available for Trino / Iceberg table and incremental models.
  The table is created with `format = 'PARQUET'` and the selected partition
  columns.

Trino models use the datasource catalog and create the project schema when
needed. Other SQL datasources use the configured schema.

## Tests

Tests run after materialization:

| Kind | Meaning |
|---|---|
| `not_null` | column has no nulls |
| `unique` | column has no duplicates |
| `accepted_values` | every non-null value is in the list |
| `relationships` | every value exists in another published model |
| `sql` | custom read-only query; a positive first value means failure |

A failing test marks the job failed, stores the results in the job payload and
raises an alert through the normal job failure path. Tests are structural
validation at publish time and execute at run time.

## Column definitions and inference

Each column can declare a name, type, source and description. The source is a
column name or `ref.column`; model lineage uses it to draw column-level edges.

**Infer from SQL** parses the model query and fills blank sources:

- a direct projection (`city`) maps to the parent model column;
- a single-column expression (`upper(city) as city_upper`) maps to that column;
- expressions touching several columns are left blank for manual review;
- joins use table aliases to choose the parent;
- manual sources are never overwritten.

Inference needs published references and a single SELECT statement.

## Preview and target

- **Preview** compiles refs, runs the query with a bounded limit and returns
  columns, rows and SQL without materializing.
- The header shows the physical target name (`catalog.schema.table` for
  Trino).

## Scheduling and operations

- Models have a cron, an enabled flag and the same dependency window as
  pipelines.
- The scheduler enqueues a `model` job, and the worker materializes it.
- Run history is the normal job history in the operations centre.
- Manual **Run** enqueues the same job.
- Publishing goes through the approval token flow; rollback republishes an
  older version and resyncs dependencies.
