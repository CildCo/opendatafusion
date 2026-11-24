# Connector SDK

The connector registry is the single source of truth for datasource types.
External packages can add a connector without forking the core by calling
`register_connector()` at import time.

## Plugin contract

A plugin is an importable Python module with a `register()` function:

```python
from odf.connectors.registry import field, register_connector


class DemoSettings:
    def __init__(self, spec):
        self.path = spec["path"]


class DemoSource:
    def __init__(self, ds, dag):
        self.ds = ds
        self.dag = dag

    def read(self, cursor, limit):
        # return (rows, next_cursor)
        return [], cursor


def register():
    register_connector(
        {
            "kind": "demo",
            "label": "Demo database",
            "group": "database",
            "capabilities": {
                "test": True,
                "metadata": True,
                "query": True,
                "source": True,
                "sink": False,
                "cdc": False,
            },
            "fields": [
                field("host"),
                field("port", default=9000),
                field("database"),
                field("username"),
                field("password"),
            ],
        },
        source_factory=DemoSource,
    )
```

- `kind` must match `[a-z][a-z0-9_]{1,31}` and must not collide with a built-in.
- `fields` reuse the built-in field definitions (`host`, `port`, `database`,
  `username`, `password`, and so on) so the console renders the same form.
- `source_factory(datasource, dag)` must return an object with
  `read(cursor, limit) -> (rows, next_cursor)`.
- `sink_factory(datasource, dag)` must return an object with
  `write(rows) -> int`.
- Capability flags are enforced by the API, metadata sync, query paths, quality
  rules and console actions. Do not advertise a capability the plugin does not
  implement.

## Airbyte connectors

The built-in `airbyte` type runs any connector that implements the Airbyte
protocol instead of a Python plugin. Platform administrators enable it and
set image/command allowlists; see [Airbyte connectors](AIRBYTE.md).

## Loading plugins

Set `ODF_CONNECTOR_PLUGINS` to a comma-separated list of module names:

```bash
ODF_CONNECTOR_PLUGINS=acme_odf_demo,acme_odf_warehouse
```

Install the plugin package into the API, worker and scheduler environments.
The module is imported when the connector registry loads; a missing module or
an invalid spec fails startup instead of advertising a broken connector.

## DSN handling

Plugins may use the generic form DSN builder provided by the registry, or
return a custom DSN from their own factory. Secrets must be declared with
`"secret": true` in the field definition so the console masks them and does not
return them from list APIs.

## Verification checklist

1. `GET /api/v1/datasources/connectors` lists the new type with its fields.
2. Create a datasource, test the connection, and sync metadata if supported.
3. Run one query or pipeline if the capability is declared.
4. Confirm list APIs mask every secret field.
5. Add a backend test that registers the plugin and builds its source/sink.
