# Scale benchmark

A reproducible benchmark for OpenDataFusion. It generates a 30GB Chinese
e-commerce and event dataset, runs PostgreSQL-backed pipelines, exercises
real dataset/metric/dashboard queries, injects faults, and validates recovery.

## Requirements

- Linux host with PostgreSQL 14+ client/server binaries and Python 3.11
- 48 cores and at least 35GB free RAM recommended for the 30GB profile
- At least 500GB free disk for data, indexes, WAL and temporary files
- No Docker required
- A separate PostgreSQL cluster and ports; do not point this at a production
  control database

The benchmark is destructive by design: it creates its own PostgreSQL cluster
and removes its root directory during cleanup. Run it on a disposable host or
in a disposable directory, never next to a database you care about.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `ODF_BENCH_ROOT` | `/data/odf-bench` | Isolated benchmark root |
| `ODF_BENCH_PYTHON` | current interpreter | Python used for API/worker/scheduler |
| `ODF_BENCH_APP_SOURCE` | `../impl` from this repository | Application source copied into the bench |
| `ODF_BENCH_PG_BIN` | `/opt/pgsql-14.5/bin` | PostgreSQL binaries |

Set `ODF_BENCH_PYTHON` and `ODF_BENCH_APP_SOURCE` if the defaults do not match
your checkout.

## Run

```bash
export ODF_BENCH_ROOT=/data/odf-bench
export ODF_BENCH_PYTHON=/path/to/python
export ODF_BENCH_APP_SOURCE=/path/to/opendatafusion/impl

mkdir -p "$ODF_BENCH_ROOT"
cp -a bench "$ODF_BENCH_ROOT/bench"
cd "$ODF_BENCH_ROOT"
./bench/run.sh preflight
./bench/run.sh setup
./bench/run.sh generate
./bench/run.sh test targeted   # ~25 min real-query profile
./bench/run.sh test full       # ~4 hour profile
./bench/run.sh report
./bench/run.sh cleanup
```

`test targeted` seeds tenants/assets, runs dataset preview, metric query,
dashboard data, catalog, list and MCP traffic, and applies a runtime guard
that aborts when free memory, disk, load or the production readiness probe
leaves its safety envelope.

`test full` adds the long baseline/peak/fault/soak phases.

## Cleanup

`cleanup` stops benchmark processes, stops the isolated PostgreSQL cluster and
deletes `ODF_BENCH_ROOT`. It refuses to delete a directory without the
`.odf-bench-root` marker. It does not touch any other database, service or
installation.

## Results

Published benchmark results and the cache experiments are summarised in
[`docs/BENCHMARKS.md`](../docs/BENCHMARKS.md). Raw result JSON is intentionally
kept out of the repository so that runs remain reproducible without committing
machine-specific files.
