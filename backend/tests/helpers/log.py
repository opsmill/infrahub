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


class _RecordCollector(logging.Handler):
    def __init__(self, records: list[logging.LogRecord], level: int) -> None:
        super().__init__(level=level)
        self._records = records

    def emit(self, record: logging.LogRecord) -> None:
        self._records.append(record)


@contextmanager
def capture_log_records(logger_name: str, level: int) -> Iterator[list[logging.LogRecord]]:
    """Collect what one logger emits at ``level`` or above inside the block, then put its level and handlers back.

    Meant for a class-scoped fixture, whose logs land in whichever test happens to set it up first.
    """
    records: list[logging.LogRecord] = []
    handler = _RecordCollector(records=records, level=level)
    target = logging.getLogger(logger_name)
    previous_level = target.level
    target.addHandler(handler)
    target.setLevel(level)
    try:
        yield records
    finally:
        target.removeHandler(handler)
        target.setLevel(previous_level)


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


def infrahub_log_payloads(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    """Return the infrahub logger's structured payloads in order, without timestamps, so each compares whole."""
    return [
        {name: value for name, value in record.msg.items() if name != "timestamp"}
        for record in caplog.records
        if record.name == "infrahub" and isinstance(record.msg, dict)
    ]
