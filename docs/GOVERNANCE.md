# Data governance

## Column classification and masking

Policies are stored per physical column (`datasource + schema + table +
column`), so metadata re-sync does not lose them.

- Classifications: `pii`, `confidential`, `sensitive`.
- Mask types: `redact` (`***`), `partial` (keeps a small prefix/suffix),
  `hash` (stable truncated SHA-256), `null`.
- Admin always sees the original value. Other roles are masked unless listed
  in the policy's exempt roles.
- CRUD: `GET/POST /api/v1/datasets/{id}/column-policies` and
  `DELETE /api/v1/datasets/{id}/column-policies/{policy_id}`.
- UI: dataset editor → **字段脱敏**.

Masking is applied to:

- dataset preview/query and all dashboards/apps/share links that use them
- metric dimensions and aggregate outputs (except `count(*)`)
- visual API preview and external API responses (role `viewer`)
- MCP dataset/metric reads

## Raw SQL boundary

Arbitrary SQL cannot be rewritten safely for column masks. Therefore:

- SQL-mode APIs are rejected when their datasource has any column policy.
- Workbench and federation are disabled for non-admins on governed
  datasources.
- MCP `query_sql` and SQL-mode API endpoints are rejected for governed
  datasources.

Use visual datasets/APIs so masks and aliases are known. This is a deliberate
enterprise trade-off: governed data cannot be exported wholesale through an
unconstrained SQL surface.

## Quality rules

Supported kinds:

| Kind | Config |
| --- | --- |
| `not_null` | column |
| `unique` | column |
| `row_count` | `min`, `max` |
| `range` | column, `min`, `max` |
| `freshness` | column, `max_age_hours` |
| `regex` | column, `pattern`, `allow_null` |
| `accepted_values` | column, `values`, `allow_null` |
| `schema` | `expected`, `allow_extra` |

Regex and accepted-value checks scan up to 100,000 rows per run. Freshness
requires a timestamp column; date-only values are treated as UTC midnight.

## Lineage impact

`GET /api/v1/catalog/impact?ref={datasource_id}:{table}` walks downstream
table/asset edges and returns affected nodes plus column edges. The catalog
detail card shows the downstream list.

## CDC boundary

The platform currently implements **incremental cursor ingestion + bounded
backfill**, not log-based CDC:

- captures new/updated rows ordered by a cursor column
- does not capture hard deletes or before-images
- latest rows are visible only after the next cursor run
- `end_cursor` backfill replays a bounded range without moving the production
  cursor

For true CDC, run Debezium/Kafka Connect or native logical replication and land
changes into a staging table, then consume that table with a cursor pipeline.
A native PostgreSQL logical-replication consumer is a separate future module,
not part of the current governance baseline.

## Known limitation

App Studio edit forms that expose a masked column should not be used to update
that column: the form reads masked values. Use a dedicated write API over a
non-sensitive table, or exclude the field from the form.

## Data contracts

Every dataset and transform model can carry a contract in
`asset.contract_json`. The contract is edited from **Governance → Data
contracts** or through `PUT /api/v1/assets/{id}/governance`.

Shape:

```json
{
  "owner": "data-team",
  "sla": "daily by 07:00",
  "notes": "",
  "enforce": true,
  "allow_extra": true,
  "schema": [
    {"name": "order_id", "type": "bigint", "required": true},
    {"name": "total", "type": "double"}
  ],
  "quality": [],
  "freshness": {"column": "updated_at", "max_hours": 24},
  "schedule": "0 0 6 * * *"
}
```

- **Generate** reads the live table structure and writes the `schema` list.
  Datasets resolve their table through the asset query; models resolve their
  physical target.
- **Check** compares expected columns with the live table: missing columns,
  type differences and, when `allow_extra` is false, unexpected columns.
  Type comparison ignores parameters and casing, so `varchar(32)` matches
  `varchar`.
- **Enforce** makes a model run fail when the check does not pass. The job
  error names the missing columns and follows the normal alert path.
- Checks run when requested and after every model materialization. Dataset
  contracts are checked on demand so that previews stay cheap.
- **Freshness** queries `MAX(<column>)` on the live table and reports an issue
  when it is older than `max_hours`, empty or not a time value. Leave the
  column blank to disable it.
- **Quality checks** run against the live table: `not_null`, `unique`,
  `accepted_values`, `max_null_pct` and a read-only `sql` check whose first
  value must be zero. The console edits them per contract.
- **Schedule** runs the check on a six-field cron (`sec min hour dom mon
  dow`). The scheduler queues a `contract` job through the normal queue;
  results are stored in `contract_check` and the history is available in the
  governance console. A failed check fails the job and follows the alert path.
- Supported asset types are datasets and models; other types return an error.

## Classification propagation

Publishing a transform model copies column policies from its sources:

- source table columns with a policy, when the model reads one raw table;
- parent model columns, when the model uses `{{ ref('key') }}`.

The model's physical target receives matching `pii` / `confidential` /
`sensitive` policies with the same mask type and exempt roles, marked with
source `lineage`. Columns that no longer have a propagated source are removed
on the next publish. A manually created policy is never overwritten.

Checking a Trino model uses `DESCRIBE <catalog>.<schema>.<table>`. Other SQL
datasources use SQLAlchemy column inspection.


## Asset sharing across projects

Published APIs, datasets and models can be requested by another project:

- `POST /api/v1/asset-requests` with an asset id, or `by-key` with an asset
  key; `GET` lists outgoing or incoming requests.
- Approvers decide through `POST /asset-requests/{id}/approve|reject`.
- Active grants are listed by `GET /asset-grants` and revoked with `DELETE`.
- `GET /shared-assets` lists assets granted to the current project.

The receiving project gets read-only access:

- APIs keep the existing AK/SK gateway path.
- Datasets can be previewed from their published version with column masking
  applied; `/shared-assets/{id}/preview` strips the generated SQL.
- Models expose layer, materialization, physical target and declared columns
  only; SQL and editing stay with the owner project.

Migrations rename `interface_grant`/`interface_request` to
`asset_grant`/`asset_request` and add `asset_type`; existing rows become
`api`. The old `/api-*` routes remain as API-only aliases.

## Quality SLA and trends

`GET /api/v1/quality/trends?days=30` returns per-rule runs, pass rate,
failure streak, SLA percentage and daily pass/fail buckets. The SLA is stored
in the rule configuration as `sla_percent`; the console marks rules whose
recent pass rate is below it.

After a scheduled or manual run, a rule whose 30-day pass rate is below its
SLA raises a `quality SLA breach` alert through the normal alert path. Open
alerts are deduplicated by title.
