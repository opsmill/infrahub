from collections.abc import Iterator

import pytest

from infrahub import lock
from tests.adapters.lock import LockTimeline, install_recording_lock_registry


@pytest.fixture
def recording_lock_timeline() -> Iterator[LockTimeline]:
    """Swap the global lock registry for a recording one, restoring the original on teardown."""
    original = lock.registry
    timeline = install_recording_lock_registry()
    try:
        yield timeline
    finally:
        lock.registry = original
