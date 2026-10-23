#!/usr/bin/env bash
set -euo pipefail
ROOT="${ODF_BENCH_ROOT:-/data/odf-bench}"
PY="${ODF_BENCH_PYTHON:-python}"
cd "$ROOT"
export PYTHONPATH="$ROOT"

case "${1:-}" in
  preflight) "$PY" -m bench.preflight ;;
  setup)
    "$PY" -m bench.setup_env
    ;;
  generate)
    "$PY" -c "from bench import config; from bench.generate import shop; shop.generate(config.ROOT)"
    "$PY" -c "from bench import config, pg; from bench.generate import load; print(load.load_all(config.ROOT, pg.dsn('shop')))"
    "$PY" -c "from bench import config; from bench.generate import files; print(files.build(config.ROOT))"
    "$PY" -c "from bench import config; from bench.generate import edge; print(edge.build(config.ROOT))"
    ;;
  test) "$PY" -m bench.runner --profile "${2:-full}" ;;
  report) cat "$ROOT/report/report.md" ;;
  cleanup) "$PY" -m bench.cleanup --root "$ROOT" ;;
  *) echo "usage: $0 {preflight|setup|generate|test|report|cleanup}" ; exit 2 ;;
esac
