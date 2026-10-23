from bench import runner


def test_profile_phases():
    assert runner.phases("smoke")[0][0] == "warmup"
    assert runner.phases("smoke")[-1][0] == "smoke"
    assert runner.phases("full") == runner.config.PHASES


def test_targeted_profile_is_short_and_has_real_load():
    assert runner.phases("targeted")[1] == ("mixed", 15, 50)
