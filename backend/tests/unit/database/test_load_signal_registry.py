from __future__ import annotations

from infrahub import config
from infrahub.database.load_signal_registry import get_reference_query_load_tracker


def test_tracker_is_shared_across_callers() -> None:
    # The database layer feeds the tracker and the admission gate reads it, so the gate would
    # decide against an empty signal if repeated calls handed back separate instances.
    assert get_reference_query_load_tracker() is get_reference_query_load_tracker()


def test_tracker_window_comes_from_settings() -> None:
    tracker = get_reference_query_load_tracker()

    assert tracker.window_seconds == config.SETTINGS.api.backpressure_stress_window_seconds
