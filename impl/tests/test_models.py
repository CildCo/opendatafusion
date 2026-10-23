from odf.models import Flow, FlowRun


def test_flow_defaults():
    f = Flow(project_id=1, name="demo", cron="0 */5 * * * ?", status=0)
    assert f.current_version == 1


def test_flowrun_status_values():
    r = FlowRun(flow_id=1, status=0)
    assert r.status in (0, 1, 2, 3, 4)
