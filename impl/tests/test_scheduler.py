from odf.services.scheduler import cron_to_trigger


def test_cron():
    trigger = cron_to_trigger("0 */5 * * * ?")
    assert trigger is not None


def test_project_timezone_is_used_for_cron():
    from datetime import datetime, timezone
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from odf.db import Base
    from odf.models import Project
    from odf.services.scheduler import cron_to_trigger, project_timezone
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=77, code="tz", name="tz",
                  quota_json={"timezone": "Asia/Shanghai"}))
    s.commit()
    tz = project_timezone(s, 77)
    assert str(tz) == "Asia/Shanghai"
    trigger = cron_to_trigger("0 0 9 * * ?", tz)
    assert str(trigger.timezone) == "Asia/Shanghai"
    nxt = trigger.get_next_fire_time(
        None, datetime(2026, 11, 26, 0, 0, tzinfo=timezone.utc))
    assert nxt.hour == 9
