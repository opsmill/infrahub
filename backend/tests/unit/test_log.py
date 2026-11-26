from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import ALWAYS_OFF

from infrahub.log import (
    _TRACEBACK_SUPPRESSED_TYPES,
    PREFECT_RUN_LOGGERS,
    TracebackSuppressionFilter,
    add_trace_id,
    suppress_traceback_in_logs,
)
from infrahub.webhook.classifier import ClassifiedFailure, StatusClass, WebhookDeliveryError
from tests.helpers.log import traceback_suppression

if TYPE_CHECKING:
    from collections.abc import Sequence


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


def test_drops_traceback_for_registered_type() -> None:
    failure = ClassifiedFailure(
        status_class=StatusClass.HTTP_CLIENT_ERROR, message="The target responded with HTTP 404."
    )
    suppression_filter = TracebackSuppressionFilter({WebhookDeliveryError})
    assert suppression_filter.filter(_record(WebhookDeliveryError(failure))) is False


def test_keeps_traceback_for_unregistered_type() -> None:
    suppression_filter = TracebackSuppressionFilter({WebhookDeliveryError})
    assert suppression_filter.filter(_record(RuntimeError("boom"))) is True


def test_keeps_records_without_an_exception() -> None:
    assert TracebackSuppressionFilter(set()).filter(_record(None)) is True


def test_decorator_registers_type_in_the_shared_registry() -> None:
    @suppress_traceback_in_logs
    class _ExpectedFailureError(Exception): ...

    # The production filter is wired to this shared registry, so a decorated type is suppressed.
    assert TracebackSuppressionFilter(_TRACEBACK_SUPPRESSED_TYPES).filter(_record(_ExpectedFailureError())) is False


def test_startup_installs_the_filter_on_the_prefect_run_loggers() -> None:
    """Importing infrahub.log configures logging for the process, which is what installs the filter."""
    installed_on = [
        name
        for name in PREFECT_RUN_LOGGERS
        if any(isinstance(log_filter, TracebackSuppressionFilter) for log_filter in logging.getLogger(name).filters)
    ]
    assert installed_on == list(PREFECT_RUN_LOGGERS)


def _run_logger_filters() -> dict[str, Sequence[object]]:
    # Logger.filters is a union of filter forms; the identity of what is attached is all that matters here.
    return {name: list(logging.getLogger(name).filters) for name in PREFECT_RUN_LOGGERS}


def test_traceback_suppression_leaves_logging_state_unchanged() -> None:
    """The suppression context must hand logging back exactly as it found it."""
    root_logger = logging.getLogger()
    level_before, filters_before = root_logger.level, _run_logger_filters()

    with traceback_suppression() as traceback_filter:
        assert _run_logger_filters() == {
            name: [*filters_before[name], traceback_filter] for name in PREFECT_RUN_LOGGERS
        }
        assert root_logger.level == level_before

    assert _run_logger_filters() == filters_before
    assert root_logger.level == level_before


def test_line_inside_a_recording_span_carries_its_trace_id() -> None:
    provider = TracerProvider()
    with provider.get_tracer(__name__).start_as_current_span("flow run") as span:
        event = add_trace_id(logger=None, method_name="info", event_dict={"event": "flow started"})
        expected = format(span.get_span_context().trace_id, "032x")

    assert re.fullmatch(r"[0-9a-f]{32}", event["trace_id"])
    assert event == {"event": "flow started", "trace_id": expected}


def test_line_outside_a_span_has_no_trace_id() -> None:
    assert add_trace_id(logger=None, method_name="info", event_dict={"event": "flow started"}) == {
        "event": "flow started"
    }


def test_line_inside_a_span_that_is_not_recorded_has_no_trace_id() -> None:
    provider = TracerProvider(sampler=ALWAYS_OFF)
    with provider.get_tracer(__name__).start_as_current_span("flow run"):
        event = add_trace_id(logger=None, method_name="info", event_dict={"event": "flow started"})

    assert event == {"event": "flow started"}


def test_line_that_already_has_a_trace_id_keeps_it() -> None:
    provider = TracerProvider()
    with provider.get_tracer(__name__).start_as_current_span("request"):
        event = add_trace_id(
            logger=None, method_name="info", event_dict={"event": "request done", "trace_id": "from-the-request"}
        )

    assert event == {"event": "request done", "trace_id": "from-the-request"}
