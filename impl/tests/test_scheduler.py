from odf.services.scheduler import cron_to_trigger


def test_cron():
    trigger = cron_to_trigger("0 */5 * * * ?")
    assert trigger is not None
