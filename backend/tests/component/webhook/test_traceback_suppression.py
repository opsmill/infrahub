from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from prefect import flow

from infrahub.log import configure_logging
from infrahub.webhook.classifier import ClassifiedFailure, StatusClass, WebhookDeliveryError

if TYPE_CHECKING:
    from collections.abc import Generator

PREFECT_FLOW_RUN_LOGGER = "prefect.flow_runs"
CLASSIFIED_MESSAGE = "The target responded with HTTP 404."
TRACEBACK_HEADER = "Traceback (most recent call last)"


@flow(name="raise-classified-failure")
async def _raise_classified_failure() -> None:
    raise WebhookDeliveryError(
        ClassifiedFailure(status_class=StatusClass.HTTP_CLIENT_ERROR, message=CLASSIFIED_MESSAGE)
    )


@flow(name="raise-unclassified-failure")
async def _raise_unclassified_failure() -> None:
    raise RuntimeError("boom")


class _RecordingHandler(logging.Handler):
    """Collect the formatted output — traceback included — of every record the logger lets through."""

    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter("%(message)s"))
        self.output: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.output.append(self.format(record))


@pytest.fixture
def flow_run_output() -> Generator[list[str], None, None]:
    # Run the real wiring that registers the traceback filter on the Prefect run loggers, then observe
    # what actually reaches a handler when Prefect's engine logs a failed run.
    configure_logging(production=False, log_level="DEBUG")
    handler = _RecordingHandler()
    logger = logging.getLogger(PREFECT_FLOW_RUN_LOGGER)
    logger.addHandler(handler)
    try:
        yield handler.output
    finally:
        logger.removeHandler(handler)


async def test_classified_failure_logs_no_traceback(flow_run_output: list[str]) -> None:
    state = await _raise_classified_failure(return_state=True)

    assert state.is_failed()
    combined = "\n".join(flow_run_output)
    # No stacktrace reaches the run logs...
    assert TRACEBACK_HEADER not in combined
    # ...while the classified reason is still reported.
    assert CLASSIFIED_MESSAGE in combined


async def test_unclassified_failure_logs_a_traceback(flow_run_output: list[str]) -> None:
    state = await _raise_unclassified_failure(return_state=True)

    assert state.is_failed()
    combined = "\n".join(flow_run_output)
    assert TRACEBACK_HEADER in combined
    assert "RuntimeError: boom" in combined
