import asyncio
import json
from pathlib import Path

from bench import config

MODE_FILE = config.ROOT / "fault-mode.json"


def set_mode(delay_ms: int = 0, fail: bool = False) -> None:
    Path(MODE_FILE).parent.mkdir(parents=True, exist_ok=True)
    Path(MODE_FILE).write_text(json.dumps(
        {"delay_ms": int(delay_ms), "fail": bool(fail)}), encoding="utf-8")


def read_mode() -> dict:
    try:
        return json.loads(Path(MODE_FILE).read_text(encoding="utf-8"))
    except Exception:
        return {"delay_ms": 0, "fail": False}


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            mode = read_mode()
            if mode.get("fail"):
                break
            delay = max(0, int(mode.get("delay_ms", 0))) / 1000
            if delay:
                await asyncio.sleep(delay)
            writer.write(data)
            await writer.drain()
    finally:
        writer.close()


async def _handle(client_reader: asyncio.StreamReader,
                  client_writer: asyncio.StreamWriter,
                  target_port: int) -> None:
    if read_mode().get("fail"):
        client_writer.close()
        return
    target_reader, target_writer = await asyncio.open_connection(
        "127.0.0.1", target_port)
    await asyncio.gather(
        _pipe(client_reader, target_writer),
        _pipe(target_reader, client_writer))


async def _serve(listen_port: int, target_port: int) -> None:
    async def handler(reader, writer):
        await _handle(reader, writer, target_port)

    server = await asyncio.start_server(handler, "127.0.0.1", listen_port)
    async with server:
        await server.serve_forever()


def serve(listen_port: int = config.PROXY_PORT,
          target_port: int = config.PG_PORT) -> None:
    asyncio.run(_serve(listen_port, target_port))


if __name__ == "__main__":
    serve()
