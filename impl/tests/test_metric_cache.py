import time

from odf.modelstudio import cache


def test_cache_put_get_expiry_and_size():
    cache.clear()
    cache.put("a", {"v": 1}, ttl_s=60, max_size=2)
    assert cache.get("a") == {"v": 1}
    cache.put("b", {"v": 2}, ttl_s=60, max_size=2)
    cache.put("c", {"v": 3}, ttl_s=60, max_size=2)
    assert cache.get("a") is None
    assert cache.get("c") == {"v": 3}
    cache.put("d", {"v": 4}, ttl_s=0, max_size=2)
    assert cache.get("d") is None
    cache.clear()
    assert cache.get("b") is None
