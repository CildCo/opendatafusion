from random import Random

from bench.generate import dimensions


def test_chinese_name_is_deterministic_and_chinese():
    a = dimensions.chinese_name(Random(1))
    b = dimensions.chinese_name(Random(1))
    assert a == b
    assert 2 <= len(a) <= 4
    assert all("一" <= ch <= "鿿" for ch in a)


def test_phone_and_address_shapes():
    phone = dimensions.phone(Random(2))
    assert phone.startswith("1") and phone.isdigit() and len(phone) == 11
    address = dimensions.address(Random(3))
    assert "省" in address or "市" in address


def test_product_name_is_chinese():
    name = dimensions.product_name(Random(4))
    assert any("一" <= ch <= "鿿" for ch in name)
