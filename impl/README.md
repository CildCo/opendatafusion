# OpenDataFusion backend

The FastAPI API, MCP server, scheduler and workers live in this package.
Install and run instructions are in the repository [README](../README.md).

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn odf.main:app --host 127.0.0.1 --port 18080
```
