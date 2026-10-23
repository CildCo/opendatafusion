from random import Random

WEIGHTS = {
    "dataset_preview": 25,
    "metric": 20,
    "dashboard": 20,
    "catalog": 15,
    "dataset_list": 10,
    "ops": 5,
    "mcp": 5,
}

PHASE_END = {"warmup": 15 * 60, "baseline": 60 * 60, "peak": 120 * 60,
             "fault": 165 * 60, "cooldown": 180 * 60, "soak": 240 * 60}


def phase_at(elapsed_s: float) -> str:
    for name, end in PHASE_END.items():
        if elapsed_s < end:
            return name
    return "soak"


def pick(rng: Random) -> str:
    choice = rng.uniform(0, 100)
    total = 0
    for name, weight in WEIGHTS.items():
        total += weight
        if choice <= total:
            return name
    return "catalog"
