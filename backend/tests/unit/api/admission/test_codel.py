from __future__ import annotations

from infrahub.api.admission.codel import CoDelController

TARGET = 0.005
INTERVAL = 0.1
HIGH_MULTIPLIER = 4.0


class FakeClock:
    """Mutable monotonic clock advanced by hand; no real sleeps in CoDel tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_burst_shorter_than_interval_never_drops() -> None:
    clock = FakeClock()
    controller = CoDelController(target=TARGET, interval=INTERVAL, clock=clock)

    above_target = TARGET * 10
    drops = 0
    # Stay above target the whole time but never span a full interval.
    for _ in range(5):
        if controller.should_drop(sojourn=above_target):
            drops += 1
        clock.advance(INTERVAL / 10)

    assert clock.now < INTERVAL
    assert drops == 0


def test_sustained_overload_starts_dropping_after_one_interval() -> None:
    clock = FakeClock()
    controller = CoDelController(target=TARGET, interval=INTERVAL, clock=clock)

    above_target = TARGET * 10

    # First above-target sample only arms the interval timer; nothing drops yet.
    assert controller.should_drop(sojourn=above_target) is False

    # Still within the interval window: no drop.
    clock.advance(INTERVAL / 2)
    assert controller.should_drop(sojourn=above_target) is False

    # A full interval of continuous overload has now elapsed: dropping begins.
    clock.advance(INTERVAL / 2)
    assert controller.should_drop(sojourn=above_target) is True


def test_single_below_target_sample_exits_dropping() -> None:
    clock = FakeClock()
    controller = CoDelController(target=TARGET, interval=INTERVAL, clock=clock)

    above_target = TARGET * 10
    controller.should_drop(sojourn=above_target)
    clock.advance(INTERVAL)
    assert controller.should_drop(sojourn=above_target) is True

    # One sample under target must leave the dropping state immediately (bounded recovery).
    clock.advance(INTERVAL / 10)
    assert controller.should_drop(sojourn=TARGET / 2) is False

    # A fresh overload excursion must re-arm the interval timer rather than drop at once.
    clock.advance(INTERVAL / 10)
    assert controller.should_drop(sojourn=above_target) is False


def test_high_priority_target_protects_from_shedding() -> None:
    clock = FakeClock()
    normal = CoDelController(target=TARGET, interval=INTERVAL, clock=clock)
    high = CoDelController(target=TARGET * HIGH_MULTIPLIER, interval=INTERVAL, clock=clock)

    # A sojourn between the two targets: above NORMAL's target, below HIGH's.
    sojourn = TARGET * 2
    assert TARGET < sojourn < TARGET * HIGH_MULTIPLIER

    normal_dropped = False
    high_dropped = False
    for _ in range(10):
        if normal.should_drop(sojourn=sojourn):
            normal_dropped = True
        if high.should_drop(sojourn=sojourn):
            high_dropped = True
        clock.advance(INTERVAL / 2)

    # Same sojourn, same clock: NORMAL sheds once the interval elapses while HIGH, with its
    # larger target, treats the sojourn as acceptable and never sheds.
    assert normal_dropped is True
    assert high_dropped is False
