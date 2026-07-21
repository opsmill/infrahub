from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from infrahub.api.admission.controller import (
    AdmissionController,
    Admitted,
    Rejected,
    stress_shed_fraction,
)
from infrahub.api.admission.priority import Priority
from infrahub.api.admission.slot_pool import PrioritySlotPool

# Per-class stress triggers (the ratio at which a class starts shedding).
_THRESHOLDS = {Priority.HIGH: 100.0, Priority.MEDIUM: 20.0, Priority.LOW: 5.0}


class _StepClock:
    """Clock that advances a fixed step on every read.

    Driving both the slot pool and the CoDel controllers with it forces an above-target
    sojourn and advances past the CoDel interval between samples, so a queued request is shed
    by CoDel by construction rather than by racing the wall clock.
    """

    def __init__(self, *, step: float) -> None:
        self._step = step
        self._now = 0.0

    def __call__(self) -> float:
        value = self._now
        self._now += self._step
        return value


class _FakeLoadSignal:
    """Hand-set database-stress signal."""

    def __init__(self, *, ratio: float, samples: int) -> None:
        self._ratio = ratio
        self._samples = samples

    def stress_ratio_min(self) -> float:
        return self._ratio

    def stress_ratio_avg(self) -> float:
        return self._ratio

    def sample_count(self) -> int:
        return self._samples


def _build(
    *, ratio: float, samples: int, rng_value: float = 0.0, max_concurrency: int = 1, min_samples: int = 1
) -> tuple[AdmissionController, PrioritySlotPool]:
    slot_pool = PrioritySlotPool(max_concurrency=max_concurrency, clock=_StepClock(step=1.0))
    controller = AdmissionController(
        slot_pool=slot_pool,
        target=0.005,
        interval=1.0,
        # Neutralise the per-class CoDel target so nothing but the signal under test differs.
        high_target_multiplier=1.0,
        backstop_max_waiters=dict.fromkeys(Priority, 1000),
        stress_signal=_FakeLoadSignal(ratio=ratio, samples=samples),
        stress_thresholds=_THRESHOLDS,
        stress_min_samples=min_samples,
        retry_after=1,
        clock=_StepClock(step=1.0),
        rng=lambda: rng_value,
    )
    return controller, slot_pool


@dataclass
class _FractionCase:
    name: str
    ratio: float
    threshold: float
    expected: float


_FRACTION_CASES = [
    _FractionCase(name="below_trigger_sheds_nothing", ratio=0.5, threshold=1.0, expected=0.0),
    _FractionCase(name="at_trigger_is_mild", ratio=1.0, threshold=1.0, expected=0.20),
    _FractionCase(name="just_under_2x_is_mild", ratio=1.9, threshold=1.0, expected=0.20),
    _FractionCase(name="at_2x_is_moderate", ratio=2.0, threshold=1.0, expected=0.50),
    _FractionCase(name="just_under_5x_is_moderate", ratio=4.9, threshold=1.0, expected=0.50),
    _FractionCase(name="at_5x_is_severe", ratio=5.0, threshold=1.0, expected=0.80),
    _FractionCase(name="far_past_trigger_is_severe", ratio=100.0, threshold=1.0, expected=0.80),
    _FractionCase(name="scales_with_threshold", ratio=40.0, threshold=20.0, expected=0.50),
    _FractionCase(name="non_positive_threshold_sheds_nothing", ratio=10.0, threshold=0.0, expected=0.0),
]


@pytest.mark.parametrize("case", _FRACTION_CASES, ids=[case.name for case in _FRACTION_CASES])
def test_stress_shed_fraction(case: _FractionCase) -> None:
    assert stress_shed_fraction(ratio=case.ratio, threshold=case.threshold) == case.expected


@dataclass
class _StressCase:
    name: str
    ratio: float
    priority: Priority
    rng_value: float
    expect_shed: bool
    samples: int = 100


_STRESS_CASES = [
    # LOW trigger is 5x. ratio 7 -> 1.4x -> mild 20%.
    _StressCase(
        name="low_mild_sheds_when_draw_below_fraction",
        ratio=7.0,
        priority=Priority.LOW,
        rng_value=0.1,
        expect_shed=True,
    ),
    _StressCase(
        name="low_mild_admits_when_draw_above_fraction",
        ratio=7.0,
        priority=Priority.LOW,
        rng_value=0.5,
        expect_shed=False,
    ),
    # ratio 12 -> 2.4x -> moderate 50%.
    _StressCase(name="low_moderate_sheds", ratio=12.0, priority=Priority.LOW, rng_value=0.4, expect_shed=True),
    _StressCase(name="low_moderate_admits", ratio=12.0, priority=Priority.LOW, rng_value=0.6, expect_shed=False),
    # ratio 30 -> 6x -> severe 80%.
    _StressCase(name="low_severe_sheds", ratio=30.0, priority=Priority.LOW, rng_value=0.7, expect_shed=True),
    _StressCase(
        name="low_severe_admits_above_80pct", ratio=30.0, priority=Priority.LOW, rng_value=0.85, expect_shed=False
    ),
    # Below the trigger nothing is shed, whatever the draw.
    _StressCase(name="low_below_trigger_admits", ratio=4.0, priority=Priority.LOW, rng_value=0.0, expect_shed=False),
    # Same ratio 30 is severe for LOW, only mild for MEDIUM (trigger 20x -> 1.5x), and below
    # HIGH's trigger (100x) entirely — the trigger is per class.
    _StressCase(name="medium_mild_sheds", ratio=30.0, priority=Priority.MEDIUM, rng_value=0.1, expect_shed=True),
    _StressCase(
        name="medium_mild_admits_above_fraction", ratio=30.0, priority=Priority.MEDIUM, rng_value=0.5, expect_shed=False
    ),
    _StressCase(name="high_below_trigger_admits", ratio=30.0, priority=Priority.HIGH, rng_value=0.0, expect_shed=False),
    # Extreme ratio but too few samples to trust the floor yet.
    _StressCase(
        name="cold_window_admits", ratio=1000.0, priority=Priority.LOW, rng_value=0.0, expect_shed=False, samples=0
    ),
]


@pytest.mark.parametrize("case", _STRESS_CASES, ids=[case.name for case in _STRESS_CASES])
async def test_stress_sheds_a_fraction_without_queueing(case: _StressCase) -> None:
    """Stress sheds a graduated fraction of a class on its own, with no slot contention.

    Ample capacity means requests never queue, so CoDel never fires: the stress schedule and the
    random draw decide the outcome, and the tiered triggers decide which classes are affected.
    """
    controller, _ = _build(ratio=case.ratio, samples=case.samples, rng_value=case.rng_value, max_concurrency=10)

    result = await controller.admit(priority=case.priority)
    if isinstance(result, Admitted):
        result.acquisition.release()
        assert case.expect_shed is False
    else:
        assert case.expect_shed is True
        assert result.reason == "stress"


async def _second_follower(
    controller: AdmissionController, slot_pool: PrioritySlotPool, *, priority: Priority
) -> Admitted | Rejected:
    """Run holder + two queued followers of one class; return the second follower's decision.

    Draining the holder admits the first follower (it only arms the CoDel interval); draining
    that one pushes the second past the drop threshold, so CoDel wants to shed it.
    """
    holder = await controller.admit(priority=priority)
    assert isinstance(holder, Admitted)

    follower_a = asyncio.create_task(controller.admit(priority=priority))
    follower_b = asyncio.create_task(controller.admit(priority=priority))
    while slot_pool.waiters(priority=priority) < 2:  # noqa: ASYNC110
        await asyncio.sleep(0)

    holder.acquisition.release()
    result_a = await follower_a
    assert isinstance(result_a, Admitted)
    result_a.acquisition.release()

    result_b = await follower_b
    if isinstance(result_b, Admitted):
        result_b.acquisition.release()
    return result_b


async def test_codel_sheds_independent_of_stress() -> None:
    """With the stress signal quiet, a sojourn overrun still sheds — reported as CoDel."""
    controller, slot_pool = _build(ratio=1.0, samples=100)

    result = await _second_follower(controller, slot_pool, priority=Priority.LOW)

    assert isinstance(result, Rejected)
    assert result.reason == "codel"


async def test_stress_is_reported_when_both_triggers_fire() -> None:
    """When both the stress signal and a CoDel overrun fire, the shed is attributed to stress.

    HIGH is below its 100x trigger at 50x, so a HIGH holder occupies the slot while two LOW
    followers queue and build an above-target sojourn. LOW is severely stressed at 50x (10x its
    trigger, an 80% shed fraction) and the draw is forced below it, so the second follower — which
    also trips CoDel — is reported as stress.
    """
    controller, slot_pool = _build(ratio=50.0, samples=100, rng_value=0.0)

    holder = await controller.admit(priority=Priority.HIGH)
    assert isinstance(holder, Admitted)

    follower_a = asyncio.create_task(controller.admit(priority=Priority.LOW))
    follower_b = asyncio.create_task(controller.admit(priority=Priority.LOW))
    while slot_pool.waiters(priority=Priority.LOW) < 2:  # noqa: ASYNC110
        await asyncio.sleep(0)

    holder.acquisition.release()
    results = [await follower_a, await follower_b]
    for result in results:
        if isinstance(result, Admitted):
            result.acquisition.release()

    assert isinstance(results[1], Rejected)
    assert results[1].reason == "stress"
