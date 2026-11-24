# Templates

Templates create a draft asset with a pre-filled model or pipeline so that
common patterns do not have to be rebuilt by hand.

| Template | Type | Result |
| --- | --- | --- |
| Standard staging model | model | `select * from <table>`, table materialization, staging layer |
| Incremental merge model | model | incremental materialization, merge by `id` |
| Deduplicated mart | model | `select distinct * from <table>`, mart layer |
| Table sync pipeline | pipeline | source → sink upsert by primary key |

## Using templates

- Model list → **Templates** (visible on the transform models tab).
- Pipeline list → **Templates**.
- Select a template, choose a datasource, enter the source table and, for
  pipelines, the target datasource and table.
- The result opens in the normal editor as a draft.

## Rules

- Table names must be `table` or `schema.table` with identifier characters.
- Model templates validate the datasource and content before creating the
  asset.
- Pipeline templates validate both datasources, the target table and the
  primary key through the normal pipeline validator.
- Templates never publish, schedule or run anything.
