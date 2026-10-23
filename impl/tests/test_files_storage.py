import pytest

from odf.files.storage import LocalStorage


def test_local_storage_roundtrip(tmp_path):
    storage = LocalStorage(tmp_path)
    source = tmp_path / "source.bin"
    source.write_bytes(b"payload")
    storage.put("nested/item.bin", source)
    assert storage.exists("nested/item.bin")
    assert b"".join(storage.open("nested/item.bin")) == b"payload"
    storage.delete("nested/item.bin")
    assert not storage.exists("nested/item.bin")


@pytest.mark.parametrize("key", ["", "../outside", "../../etc/passwd",
                                 "/etc/passwd"])
def test_local_storage_rejects_escaped_keys(tmp_path, key):
    storage = LocalStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.exists(key)
