from bench.assertions import checks


def test_compare_counts_reports_mismatch():
    assert checks.compare_counts({"a": 1}, {"a": 1}) == []
    assert checks.compare_counts({"a": 1}, {"a": 2}) == ["a: 1 != 2"]


def test_cursor_ok():
    assert checks.cursor_ok("100", "100")
    assert not checks.cursor_ok("99", "100")
