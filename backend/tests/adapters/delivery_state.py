from datetime import UTC, datetime

from tests.unit.git.writeback.fakes import FixedClock, InMemoryDeliveryState


def build_idle_delivery_state() -> InMemoryDeliveryState:
    """Return a delivery state in which no repository has a pending push."""
    return InMemoryDeliveryState(clock=FixedClock(now=datetime(2026, 1, 1, tzinfo=UTC)), repository_names={})
