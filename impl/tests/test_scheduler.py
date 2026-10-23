import pytest

from odf.services.scheduler import claim_run, cron_to_trigger, release_run


def test_cron():
    t = cron_to_trigger("0 */5 * * * ?")
    assert t is not None


@pytest.mark.integration
def test_advisory_lock_blocks_second_claim():
    from odf.db import SessionLocal
    with SessionLocal() as s:
        assert claim_run(s, 1) is True
        assert claim_run(s, 1) is False
        release_run(s, 1)


def test_failed_trigger_releases_lock():
    from odf.db import SessionLocal
    from odf.models import Flow
    from odf.services.scheduler import trigger
    with SessionLocal() as s:
        f = Flow(project_id=1, name="broken",
                 cron="0 */5 * * * ?", status=1)
        s.add(f)
        s.commit()
        s.refresh(f)
        with pytest.raises(Exception):
            trigger(s, f.id, "test")
        assert claim_run(s, f.id) is True
        release_run(s, f.id)


def test_trigger_rejects_disabled_flow():
    from odf.db import SessionLocal
    from odf.models import Flow
    from odf.services.scheduler import trigger
    with SessionLocal() as s:
        f = Flow(project_id=1, name="disabled",
                 cron="0 */5 * * * ?", status=0)
        s.add(f)
        s.commit()
        s.refresh(f)
        with pytest.raises(RuntimeError):
            trigger(s, f.id, "test")


def test_schedule_registers_job():
    from odf.db import SessionLocal
    from odf.models import Flow
    from odf.services.scheduler import (_sched, schedule, start_scheduler,
                                        stop_scheduler, unschedule)
    start_scheduler()
    try:
        with SessionLocal() as s:
            f = Flow(project_id=1, name="sched",
                     cron="0 */5 * * * ?", status=1)
            s.add(f)
            s.commit()
            s.refresh(f)
            schedule(s, f.id)
            assert _sched.get_job(str(f.id)) is not None
            unschedule(f.id)
            assert _sched.get_job(str(f.id)) is None
    finally:
        stop_scheduler()
