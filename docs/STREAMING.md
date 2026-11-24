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
**Debezium envelope** enabled, so the pipeline consumes `payload.after` and
skips delete events (`payload.after = null`). Each sink upserts by the
primary key.

Target tables must exist before generation; validation reports missing tables
and unsupported datasources. The generated pipeline is a draft: review it,
schedule it, publish it through the approval flow, or edit the nodes.

## Limits

- Deletes are not propagated; a delete in the source leaves the target row in
  place. Use a model or maintenance job to reconcile deletes.
- One primary key column is used for both source and sink nodes.
- Kafka consumer offsets are stored on the pipeline asset, like any other
  Kafka pipeline.
