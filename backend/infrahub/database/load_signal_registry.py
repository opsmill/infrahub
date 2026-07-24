from __future__ import annotations

from .load_signal import ReferenceQueryLoadTracker
from .load_signal_metrics import LoadSignalMetricsObserver

_reference_query_load_tracker: ReferenceQueryLoadTracker | None = None


def get_reference_query_load_tracker() -> ReferenceQueryLoadTracker:
    """Return the process-global stress tracker, building and wiring it on first use.

    The database layer feeds it and the admission layer reads it, so both must share one
    instance. The wiring lives in this module, apart from the tracker itself, so importing the
    signal primitive never drags the metrics sink into the import chain. Building it lazily —
    rather than at import — keeps importing this module free of side effects. It starts with the
    default window; the startup wiring overrides that from settings.
    """
    global _reference_query_load_tracker
    if _reference_query_load_tracker is None:
        _reference_query_load_tracker = ReferenceQueryLoadTracker(observers=[LoadSignalMetricsObserver()])
    return _reference_query_load_tracker
