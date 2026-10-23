import copy
import threading
import time
from collections import OrderedDict

_lock = threading.Lock()
_cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()


def clear() -> None:
    with _lock:
        _cache.clear()


def get(key: str, kind: str = "cache"):
    now = time.time()
    with _lock:
        item = _cache.get(key)
        if not item:
            _hit(kind, False)
            return None
        expires, value = item
        if expires <= now:
            _cache.pop(key, None)
            _hit(kind, False)
            return None
        _cache.move_to_end(key)
        _hit(kind, True)
        return copy.deepcopy(value)


def _hit(kind: str, hit: bool) -> None:
    try:
        from odf.api.metrics import inc
        inc("query_cache_hits" if hit else "query_cache_misses", kind=kind)
    except Exception:
        pass


def put(key: str, value: dict, ttl_s: int, max_size: int = 128) -> None:
    if ttl_s <= 0:
        return
    with _lock:
        _cache[key] = (time.time() + ttl_s, copy.deepcopy(value))
        _cache.move_to_end(key)
        while len(_cache) > max(1, max_size):
            _cache.popitem(last=False)
