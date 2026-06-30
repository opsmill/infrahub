from __future__ import annotations

import logging

from infrahub.log import SuppressMarkedTracebackFilter
from infrahub.webhook.classifier import ClassifiedFailure, StatusClass, WebhookDeliveryError


def _record(exception: BaseException | None) -> logging.LogRecord:
    exc_info = (type(exception), exception, exception.__traceback__) if exception else None
    return logging.LogRecord(
        name="prefect.flow_runs",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Encountered exception during execution: %r",
        args=(exception,),
        exc_info=exc_info,
    )


def test_drops_traceback_for_marked_exception() -> None:
    failure = ClassifiedFailure(
        status_class=StatusClass.HTTP_CLIENT_ERROR, message="The target responded with HTTP 404."
    )
    assert SuppressMarkedTracebackFilter().filter(_record(WebhookDeliveryError(failure))) is False


def test_keeps_traceback_for_unmarked_exception() -> None:
    assert SuppressMarkedTracebackFilter().filter(_record(RuntimeError("boom"))) is True


def test_keeps_records_without_an_exception() -> None:
    assert SuppressMarkedTracebackFilter().filter(_record(None)) is True
