# Lineage events and catalog export

The platform can publish pipeline lineage to an OpenLineage endpoint and push
a catalog snapshot to an external catalog service. Both are platform-wide
settings under Administration → Platform → **Lineage and catalog sync**.

## OpenLineage

- **Endpoint**: any HTTP endpoint that accepts OpenLineage events, for example
  `http://marquez:5000/api/v1/lineage`.
- **Token**: optional bearer token, stored encrypted.
- **Namespace**: job and dataset namespace prefix. Default `odf`.

Events are emitted for `pipeline` and `pipeline_backfill` jobs:

| Event | When |
|---|---|
| `START` | When the worker starts the job |
| `COMPLETE` | After the job succeeds |
| `FAIL` | When execution raises; the error message is included as a run facet |

Each event contains the pipeline key as the job name, a stable run id derived
from the job id, the source node as an input dataset and the sink node as an
output dataset. Dataset names are `<datasource>.<table>` in the namespace
`<namespace>.<kind>`.

Lineage delivery never blocks a job. A failed endpoint call is ignored so the
worker is not coupled to the observability service. For a local endpoint that
resolves to a private address, enable outbound private addresses in the
deployment (`ODF_HTTP_ALLOW_PRIVATE=1`) or use a routable hostname.

**Send test event** in platform administration sends a minimal `COMPLETE`
event and reports the endpoint response as an error if it fails.

## Catalog export and push

`GET /api/v1/catalog/export` returns the current project as JSON. The document
contains:

- project code, name and environment;
- datasets with datasource, schema, table, columns, tags, domain and quality
  rules;
- assets with type, key, name, owner, domain, published and enabled state;
- lineage edges with optional column names.

The external sync sends the same document for every project in one POST:

```json
{
  "format": "odf-catalog",
  "version": 1,
  "generated_at": "2026-11-24T10:00:00+00:00",
  "projects": [{"code": "sales", "datasets": [], "assets": [], "lineage": []}]
}
```

Configure **Catalog sync endpoint** and an optional bearer token. A sync
interval in minutes enables automatic pushes; `0` keeps manual sync only.
**Sync now** pushes immediately and records the audit entry `catalog_sync`.
The platform stores the last sync timestamp and project count in its settings.

The receiver should treat each POST as a full snapshot for the listed
projects and replace its copy idempotently.
