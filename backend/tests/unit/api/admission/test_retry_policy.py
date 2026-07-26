from __future__ import annotations

from infrahub.api.admission.retry_policy import RetryAfterPolicy


class FakeClock:
    """Manually advanced monotonic clock so the overload episode is deterministic in tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _policy(clock: FakeClock | None = None) -> tuple[RetryAfterPolicy, list[float]]:
    """Build a policy plus a recorder capturing the sustained-load values it pushes to its observer."""
    policy = RetryAfterPolicy(
        level1_seconds=1,
        level2_seconds=5,
        level3_seconds=10,
        max_seconds=30,
        significant_load_ratio=20.0,
        sustained_warn_seconds=60.0,
        sustained_high_seconds=300.0,
        clock=clock or FakeClock(),
    )
    recorded: list[float] = []
    policy.set_observer(recorded.append)
    return policy, recorded


def test_tier_maps_to_level_seconds_without_sustained_load() -> None:
    policy, _ = _policy()
    policy.observe(ratio=1.0)  # warm-up: no episode, so no escalation

    assert policy.retry_after(tier=1) == 1
    assert policy.retry_after(tier=2) == 5
    assert policy.retry_after(tier=3) == 10


def test_tier_zero_floors_to_level_one() -> None:
    policy, _ = _policy()
    policy.observe(ratio=1.0)

    # A shed with no stress tier (e.g. CoDel below the trigger) still advises the level-1 wait.
    assert policy.retry_after(tier=0) == 1


def test_warm_up_zone_never_accrues_sustained_time() -> None:
    clock = FakeClock()
    policy, recorded = _policy(clock)

    policy.observe(ratio=15.0)  # below the significant-load line (20)
    clock.advance(600)  # well past both duration tiers
    policy.observe(ratio=15.0)

    # The episode never started, so the top tier stays at its unescalated base.
    assert policy.retry_after(tier=3) == 10
    assert recorded[-1] == 0.0


def test_sustained_load_escalates_by_duration() -> None:
    clock = FakeClock()
    policy, recorded = _policy(clock)

    policy.observe(ratio=25.0)  # crosses the line -> episode starts at t=0
    assert policy.retry_after(tier=2) == 5  # <1 min -> x1

    clock.advance(60)
    policy.observe(ratio=25.0)  # 60s sustained -> warn tier -> x2
    assert policy.retry_after(tier=2) == 10
    assert recorded[-1] == 60.0

    clock.advance(300)
    policy.observe(ratio=25.0)  # 360s sustained -> high tier -> x3
    assert policy.retry_after(tier=2) == 15


def test_result_is_clamped_to_max() -> None:
    clock = FakeClock()
    policy = RetryAfterPolicy(level3_seconds=10, max_seconds=20, clock=clock)

    policy.observe(ratio=25.0)
    clock.advance(400)  # high tier -> x3 -> 30, above the cap
    policy.observe(ratio=25.0)

    assert policy.retry_after(tier=3) == 20


def test_episode_resets_when_load_clears() -> None:
    clock = FakeClock()
    policy, recorded = _policy(clock)

    policy.observe(ratio=25.0)
    clock.advance(120)
    policy.observe(ratio=25.0)
    assert policy.retry_after(tier=1) == 2  # x2 while sustained

    clock.advance(10)
    policy.observe(ratio=5.0)  # load clears -> episode resets

    assert recorded[-1] == 0.0
    assert policy.retry_after(tier=1) == 1  # back to x1
