from bench import preflight


def test_healthy_budget_passes():
    assert preflight.check_budget(35, 900, 5.9) == []


def test_low_memory_is_rejected():
    errors = preflight.check_budget(7, 900, 5.9)
    assert any("memory" in e.lower() for e in errors)


def test_low_disk_and_high_load_are_rejected():
    errors = preflight.check_budget(35, 200, 31)
    assert any("disk" in e.lower() for e in errors)
    assert any("load" in e.lower() for e in errors)
