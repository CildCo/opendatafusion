import os
import signal
import subprocess
from pathlib import Path

from bench import stack
import pyarrow as pa
import pyarrow.parquet as pq


def _pids(path: Path) -> list[int]:
    if not path.exists():
        return []
    try:
        return [int(path.read_text())]
    except ValueError:
        return []


def kill_worker(root: Path) -> list[int]:
    pids = _pids(root / "worker.pid")
    for pid in pids:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
    (root / "worker.pid").unlink(missing_ok=True)
    return pids


def stop_scheduler(root: Path) -> list[int]:
    pids = _pids(root / "scheduler.pid")
    for pid in pids:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
    (root / "scheduler.pid").unlink(missing_ok=True)
    return pids


def start_scheduler(root: Path) -> int:
    env = f"{root}/env"
    command = (f"set -a && . {env} && set +a && "
               f"cd {root}/app && {stack.PYTHON} -m odf.scheduler")
    log = open(root / "logs" / "scheduler.log", "ab")
    proc = subprocess.Popen(["bash", "-lc", command], stdout=log, stderr=log,
                            start_new_session=True)
    (root / "scheduler.pid").write_text(str(proc.pid))
    return proc.pid


def start_worker(root: Path) -> int:
    env = f"{root}/env"
    command = (f"set -a && . {env} && set +a && "
               f"cd {root}/app && {stack.PYTHON} -m odf.worker")
    log = open(root / "logs" / "worker.log", "ab")
    proc = subprocess.Popen(["bash", "-lc", command], stdout=log, stderr=log,
                            start_new_session=True)
    (root / "worker.pid").write_text(str(proc.pid))
    return proc.pid


def http_mode(mode: str) -> None:
    import httpx
    from bench import config
    httpx.post(f"http://127.0.0.1:{config.HTTP_PORT}/mode",
               json={"mode": mode}, timeout=5)


def schema_drift(path: Path) -> None:
    table = pq.read_table(path)
    extra = table.append_column(
        "new_bench_column", pa.array(["drift"] * table.num_rows))
    pq.write_table(extra, path)
