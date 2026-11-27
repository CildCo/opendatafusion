# Airbyte connectors

Weft can run an Airbyte-protocol source connector and use it as a
pipeline source. The connector must implement the Airbyte protocol commands
`check`, `discover` and `read`.

## Enable in platform administration

Administration → Platform → **Airbyte connectors**:

- **Enabled** turns the connector type on. It is off by default.
- **Image allowlist** is a comma-separated list of image prefixes, for
  example `airbyte/source-,acme/airbyte-`.
- **Command allowlist** is a comma-separated list of local executable
  prefixes. Command runtime is rejected unless a prefix matches.
- **Timeout** bounds every connector call.

Only platform administrators can change these values.

## Create a datasource

1. Data sources → New data source → **Airbyte connector**.
2. Choose the runtime:
   - `docker` runs the image through the Docker CLI with a temporary
     `/airbyte` mount that contains `config.json`, `catalog.json` and
     `state.json`.
   - `command` runs a local executable that also speaks the protocol. This is
     useful for connectors installed on the host.
3. Enter the image (for Docker) or the full command (for local runtime).
4. Enter the connector configuration as a JSON object. Fields such as API
   keys are stored encrypted and are never returned by list APIs.
5. Save, **Test**, then **Sync metadata**.

## Behaviour

- Metadata sync calls `discover` and creates one catalog table per stream
  under schema `airbyte`. Pipeline source nodes select a stream from that
  list.
- Reads create an incremental catalog when the node has a cursor column and
  pass the last Airbyte `STATE` message back as the pipeline cursor. Without a
  cursor the stream is read with `full_refresh`.
- A read stops at the pipeline batch limit. The adapter waits briefly for a
  trailing state message before stopping the connector.
- Standard output is parsed as JSON lines; logs and traces are ignored,
  stderr is kept for troubleshooting, output is capped and the process is
  killed on timeout.
- Airbyte connectors are pipeline sources only. SQL query, sink and CDC
  capabilities are not advertised.

## Security

- Running third-party images and commands is powerful. Keep the allowlists
  narrow and review every connector before enabling it.
- The Docker runtime needs a working Docker CLI on the worker host. It does
  not mount the Docker socket, and the connector receives only its temporary
  configuration directory.
- Connector configuration is stored in the encrypted datasource DSN; list and
  detail APIs mask it.
- A disabled platform switch rejects test, discovery, read and metadata sync.
