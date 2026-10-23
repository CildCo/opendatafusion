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
