"""Helpers for asserting on what the code under test logged."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from infrahub.log import PREFECT_RUN_LOGGERS, install_traceback_suppression_filter

if TYPE_CHECKING:
    from collections.abc import Iterator

    import pytest

    from infrahub.log import TracebackSuppressionFilter


@contextmanager
def traceback_suppression() -> Iterator[TracebackSuppressionFilter]:
    """Register the traceback filter on the Prefect run loggers, as production startup does, then remove it."""
    traceback_filter = install_traceback_suppression_filter()
    try:
        yield traceback_filter
    finally:
        for prefect_logger_name in PREFECT_RUN_LOGGERS:
            logging.getLogger(prefect_logger_name).removeFilter(traceback_filter)


def find_logged_events(caplog: pytest.LogCaptureFixture, *, event: str, **fields: Any) -> list[dict]:
    """Return the structured payloads of the captured log entries with the given event name and bound fields.

    Structured logs are captured as the event dict on the record, so each returned mapping carries the
    event's bound fields (level, worker id, timestamps, ...) for the caller to assert on. Pass any of those
    fields as a keyword to narrow the match; entries are returned in the order they were captured.
    """
    return [
        record.msg
        for record in caplog.records
        if isinstance(record.msg, dict)
        and record.msg.get("event") == event
        and all(record.msg.get(name) == value for name, value in fields.items())
    ]


def find_logged_event(caplog: pytest.LogCaptureFixture, *, event: str, **fields: Any) -> dict | None:
    """Return the structured payload of the first matching log entry, or ``None`` when none was captured."""
    matches = find_logged_events(caplog, event=event, **fields)
    return matches[0] if matches else None
