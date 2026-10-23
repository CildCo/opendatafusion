import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from bench import config

PYTHON = os.environ.get("ODF_BENCH_PYTHON", sys.executable)
APP_SOURCE = Path(os.environ.get(
    "ODF_BENCH_APP_SOURCE", Path(__file__).resolve().parent.parent / "impl"))


def env_lines(control_dsn: str, shop_dsn: str, mart_dsn: str,
              jwt_secret: str, fernet_key: str) -> list[str]:
    return [
        f"ODF_DATABASE_URL={control_dsn}",
        f"ODF_JWT_SECRET={jwt_secret}",
        f"ODF_FERNET_KEY={fernet_key}",
        "ODF_API_PREFIX=/api/v1",
        "ODF_DB_POOL_SIZE=20",
        "ODF_DB_MAX_OVERFLOW=40",
        "ODF_FILE_DIR=/data/odf-bench/files",
        "ODF_FILE_SOURCE_ROOTS=/data/odf-bench/files",
        "ODF_WEBHOOK_ALLOW_PRIVATE=true",
        "ODF_MCP_PORT=18182",
        "ODF_MCP_HOST=127.0.0.1",
        "ODF_METRIC_CACHE_TTL_S=60",
        "ODF_METRIC_CACHE_SIZE=256",
        "ODF_PREVIEW_CACHE_TTL_S=60",
        "ODF_PREVIEW_CACHE_SIZE=256",
        "ODF_DASHBOARD_CACHE_TTL_S=60",
        "ODF_DASHBOARD_CACHE_SIZE=256",
        "ODF_WORKER_ID=bench-worker-1",
        "ODF_LOG_JSON=true",
        f"ODF_BENCH_SHOP_DSN={shop_dsn}",
        f"ODF_BENCH_MART_DSN={mart_dsn}",
    ]


def command_lines(root: str, app: str) -> list[str]:
    base = f"cd {app} && set -a && . {root}/env && set +a && "
    return [
        base + f"{PYTHON} -m uvicorn odf.main:app --host 127.0.0.1 --port 18180",
        base + f"{PYTHON} -m uvicorn odf.main:app --host 127.0.0.1 --port 18181",
        base + f"{PYTHON} -c 'from odf.mcp.http import main; main()'",
        base + f"{PYTHON} -m odf.worker",
        base + f"{PYTHON} -m odf.scheduler",
    ]


def copy_app(src: Path = APP_SOURCE,
             dst: Path = config.ROOT / "app") -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".venv"))


def start(root: Path, app_dir: Path, env_file: Path) -> dict[str, int]:
    paths = [str(root), str(app_dir)]
    pids = {}
    for index, command in enumerate(command_lines(*paths)):
        name = ("api", "api2", "mcp", "worker", "scheduler")[index]
        log = open(root / "logs" / f"{name}.log", "ab")
        proc = subprocess.Popen(
            ["nice", "-n", "10", "ionice", "-c2", "-n7", "bash", "-lc", command],
            stdout=log, stderr=log, start_new_session=True)
        (root / f"{name}.pid").write_text(str(proc.pid))
        pids[name] = proc.pid
    return pids


def stop(root: Path) -> list[int]:
    stopped = []
    for name in ("api", "api2", "mcp", "worker", "scheduler"):
        path = root / f"{name}.pid"
        if not path.exists():
            continue
        try:
            pid = int(path.read_text())
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            stopped.append(pid)
        except (ValueError, ProcessLookupError):
            pass
        path.unlink(missing_ok=True)
    return stopped


def wait_ready(timeout_s: int = 60) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if httpx.get(f"http://127.0.0.1:{config.API_PORT}/livez",
                         timeout=2).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def seed_admin(env_file: Path, app_dir: Path = APP_SOURCE) -> None:
    command = (
        f"set -a && . {env_file} && set +a && cd {app_dir} && "
        f"{PYTHON} -m odf.cli create-project --code default --name Default && "
        f"{PYTHON} -m odf.cli create-admin --username acceptance "
        f"--password 'AcceptPassw0rd!'")
    subprocess.run(command, shell=True, check=True)
