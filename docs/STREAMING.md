# Change data capture

CDC sources are Debezium connectors managed through the console. Each source
keeps its connector name, database settings, subscribed tables and Kafka
topic prefix. Kafka stores one topic per table as
`<topic_prefix>.<schema/table>`.

## Operations

- Create, pause, resume, delete and refresh a source.
- Edit the subscribed table list; the connector configuration is updated in
  place.
- Inspect connector and task state, failed tasks and trace messages.
- Every operation is project-scoped and audited.

## Generating a pipeline

From a source row, **Create pipeline** builds a pipeline asset in the normal
pipeline editor:

1. choose a Kafka datasource and a target datasource;
2. confirm the source table list and the Kafka topics;
3. set a primary key (default `id`);
4. optionally set a target table for a single-table source.

The generator creates one branch per subscribed table (up to ten):
`cdc.source → sink`. Each source node reads its Debezium topic and has
**Debezium envelope** and **Propagate deletes** enabled. Create and update
events produce `payload.after` rows; delete events produce the
`payload.before` row with `__odf_op = delete`. Each sink runs in `cdc` mode:
delete rows remove the target row by primary key, all others upsert.

Target tables must exist before generation; validation reports missing tables
and unsupported datasources. The generated pipeline is a draft: review it,
schedule it, publish it through the approval flow, or edit the nodes.

## Limits

- Generated pipelines enable **sink schema evolution**: columns that appear in
  the source but not in the target are added with an inferred type before the
  rows are written. Manual pipelines can enable the same switch in the sink
  node configuration.
- Before writing, values are checked against the target column types; a value
  that cannot be coerced (for example text in an integer column) fails the run
  with a curated column error.
- A delete row must carry every primary-key value; otherwise the run fails.
- One primary key column is used for both source and sink nodes.
- Manual pipelines need the source switch **Propagate deletes** and sink mode
  `cdc` to get the same behaviour.
- Kafka consumer offsets are stored on the pipeline asset, like any other
  Kafka pipeline.
