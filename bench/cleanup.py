import os
import shutil
import signal
from pathlib import Path

from bench import config, pg, stack

ROOT = config.ROOT
MARKER = config.MARKER


def cleanup(root: Path) -> dict:
    root = Path(root)
    if root.exists() and not (root / MARKER).exists():
        raise ValueError(
            f"refusing to remove {root}: missing {MARKER} marker")
    stopped = stack.stop(root) if root.exists() else []
    if root.exists():
        for name in ("mock_http", "proxy"):
            path = root / f"{name}.pid"
            if path.exists():
                try:
                    pid = int(path.read_text())
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                    stopped.append(pid)
                except (ValueError, ProcessLookupError):
                    pass
        if (root / "pgdata").exists():
            pg.stop(root)
    removed = False
    if root.exists():
        shutil.rmtree(root)
        removed = True
    Path(str(root) + ".env").unlink(missing_ok=True)
    return {"root": str(root), "stopped_pids": stopped,
            "removed": removed}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(config.ROOT))
    args = parser.parse_args()
    print(cleanup(Path(args.root)))
