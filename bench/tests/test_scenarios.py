from random import Random

from bench.load import scenarios


def test_weights_sum_to_100_and_pick_is_stable():
    assert sum(scenarios.WEIGHTS.values()) == 100
    assert scenarios.pick(Random(1)) in scenarios.WEIGHTS
    assert scenarios.phase_at(0) == "warmup"
    assert scenarios.phase_at(16 * 60) == "baseline"
    assert scenarios.phase_at(10 * 3600) == "soak"
