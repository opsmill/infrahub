from __future__ import annotations


class FakeClock:
    """Manually advanced monotonic clock so admission timing is deterministic in tests."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
