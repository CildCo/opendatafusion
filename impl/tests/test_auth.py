from odf.services.auth import create_token, decode_token


def test_roundtrip():
    t = create_token(1, 2)
    d = decode_token(t)
    assert d["sub"] == "1" and d["project_id"] == 2
