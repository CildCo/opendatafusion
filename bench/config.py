import os
from pathlib import Path

ROOT = Path(os.environ.get("ODF_BENCH_ROOT", "/data/odf-bench"))
PG_PORT = 5433
PROXY_PORT = 5434
API_PORT = 18180
API2_PORT = 18181
MCP_PORT = 18182
HTTP_PORT = 18183
FAULT_PORT = 18184

DB_CONTROL = "odf_bench"
DB_SHOP = "shop"
DB_MART = "mart"
SEED = 20261022
MARKER = ".odf-bench-root"

# (name, minutes, virtual_users)
PHASES = [
    ("warmup", 15, 10),
    ("baseline", 45, 50),
    ("peak", 60, 100),
    ("fault", 45, 60),
    ("cooldown", 15, 50),
    ("soak", 60, 50),
]

BUDGET = {
    "memory_gb": 26,
    "disk_gb": 100,
    "min_free_mem_gb": 8,
    "min_free_disk_gb": 300,
    "max_load": 30,
}
