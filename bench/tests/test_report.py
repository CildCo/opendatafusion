from bench import report


def test_report_rolls_up_gates():
    data = {"counts": {"ok": True}, "checks": ["a: 1 != 2"],
            "load": {"p95_ms": 500}}
    out = report.build(data)
    assert out["passed"] is False
    assert "30GB" in report.markdown(out)
