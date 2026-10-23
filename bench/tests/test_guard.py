from bench import guard


def test_guard_reports_resource_and_production_failures():
    assert guard.check(35, 900, 5, 200) == []
    errors = guard.check(7, 200, 31, 503)
    assert any("memory" in e for e in errors)
    assert any("disk" in e for e in errors)
    assert any("load" in e for e in errors)
    assert any("readyz" in e for e in errors)
