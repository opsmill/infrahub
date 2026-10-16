from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
import structlog
from prefect.logging.handlers import APILogHandler

from infrahub import config
from infrahub.log import (
    _TRACEBACK_SUPPRESSED_TYPES,
    PREFECT_RUN_LOGGERS,
    LogMaskingFilter,
    TracebackSuppressionFilter,
    add_log_masking_filter,
    mask_personal_data,
    suppress_traceback_in_logs,
)
from infrahub.masking import MASKED_VALUE
from infrahub.webhook.classifier import ClassifiedFailure, StatusClass, WebhookDeliveryError
from infrahub.workers.infrahub_async import DEFAULT_TASK_LOGGERS, InfrahubWorkerAsync
from tests.helpers.log import traceback_suppression

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from structlog.types import EventDict


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


IDP_URL_WITH_SECRETS = "https://idp.example.com/token?code=abc-123&state=xyz-456"
IDP_URL_MASKED = "https://idp.example.com/token?[MASKED]"


def _exc_info(message: str) -> tuple[type[BaseException], BaseException, Any]:
    try:
        raise RuntimeError(message)
    except RuntimeError:
        exc_type, exc_value, exc_traceback = sys.exc_info()
    assert exc_type is not None
    assert exc_value is not None
    return exc_type, exc_value, exc_traceback


@pytest.fixture
def formatter() -> logging.Formatter:
    """The formatter of the stdout handler that configure_logging installs on the root logger."""
    (handler,) = [
        handler
        for handler in logging.getLogger().handlers
        if isinstance(handler.formatter, structlog.stdlib.ProcessorFormatter)
    ]
    assert handler.formatter is not None
    return handler.formatter


@dataclass(frozen=True)
class LogMaskingTestCase:
    name: str
    fields: dict[str, Any]
    masked_values: tuple[str, ...]
    kept_values: tuple[str, ...] = ()


LOG_MASKING_TEST_CASES: list[LogMaskingTestCase] = [
    LogMaskingTestCase(name="token", fields={"access_token": "tok-123"}, masked_values=("tok-123",)),
    LogMaskingTestCase(name="password", fields={"password": "pw-123"}, masked_values=("pw-123",)),
    LogMaskingTestCase(name="email", fields={"user_email": "jane@example.com"}, masked_values=("jane@example.com",)),
    LogMaskingTestCase(name="user_name", fields={"username": "jane"}, masked_values=("jane",)),
    LogMaskingTestCase(name="account_name", fields={"account_name": "jane"}, masked_values=("jane",)),
    LogMaskingTestCase(name="client_ip", fields={"client_ip": "192.0.2.10"}, masked_values=("192.0.2.10",)),
    LogMaskingTestCase(
        name="url_query",
        fields={"url": "https://idp.example.com/userinfo?code=abc-123"},
        masked_values=("abc-123",),
        kept_values=("https://idp.example.com/userinfo?[MASKED]",),
    ),
    LogMaskingTestCase(
        name="nested_body",
        fields={"body": {"account_id": "acc-1", "details": [{"id_token": "jwt-123"}]}},
        masked_values=("jwt-123",),
        kept_values=("acc-1",),
    ),
    LogMaskingTestCase(
        name="unrelated_keys_kept",
        fields={"branch": "main", "query_name": "device_list"},
        masked_values=(),
        kept_values=("main", "device_list"),
    ),
]


@pytest.fixture
def stdout_lines(formatter: logging.Formatter) -> Iterator[list[str]]:
    """Collect the lines that the stdout formatter renders for records of a dedicated logger."""
    lines: list[str] = []

    class _CollectingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(self.format(record))

    handler = _CollectingHandler()
    handler.setFormatter(formatter)
    logger = logging.getLogger("infrahub.test_log_masking")
    level_before = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        yield lines
    finally:
        logger.removeHandler(handler)
        logger.setLevel(level_before)
        logger.propagate = True


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in LOG_MASKING_TEST_CASES])
def test_stdout_line_masks_values_of_personal_data_keys(stdout_lines: list[str], test_case: LogMaskingTestCase) -> None:
    structlog.stdlib.get_logger("infrahub.test_log_masking").info("user signed in", **test_case.fields)

    (line,) = stdout_lines
    for value in test_case.masked_values:
        assert value not in line
    if test_case.masked_values:
        assert MASKED_VALUE in line
    for value in test_case.kept_values:
        assert value in line


def test_masking_leaves_the_logged_objects_unchanged(stdout_lines: list[str]) -> None:
    body = {"password": "pw-123"}

    structlog.stdlib.get_logger("infrahub.test_log_masking").info("user signed in", body=body)

    (line,) = stdout_lines
    assert "pw-123" not in line
    assert body == {"password": "pw-123"}


def test_stdout_line_masks_url_query_strings_in_the_message(stdout_lines: list[str]) -> None:
    structlog.stdlib.get_logger("infrahub.test_log_masking").info(f"SSO token request to {IDP_URL_WITH_SECRETS}")

    (line,) = stdout_lines
    assert IDP_URL_MASKED in line
    assert "abc-123" not in line
    assert "xyz-456" not in line


def test_stdout_line_masks_url_query_strings_in_the_exception_text(stdout_lines: list[str]) -> None:
    error = _exc_info(f"Client error '400 Bad Request' for url '{IDP_URL_WITH_SECRETS}'")

    structlog.stdlib.get_logger("infrahub.test_log_masking").error("SSO login failed", exc_info=error)

    (line,) = stdout_lines
    assert f"for url '{IDP_URL_MASKED}'" in line
    assert "abc-123" not in line
    assert "xyz-456" not in line


def test_stdout_line_of_a_standard_logger_masks_url_query_strings(stdout_lines: list[str]) -> None:
    error = _exc_info(f"Client error '400 Bad Request' for url '{IDP_URL_WITH_SECRETS}'")

    logging.getLogger("infrahub.test_log_masking").error("Request to %s failed", IDP_URL_WITH_SECRETS, exc_info=error)

    (line,) = stdout_lines
    assert f"Request to {IDP_URL_MASKED} failed" in line
    assert f"for url '{IDP_URL_MASKED}'" in line
    assert "abc-123" not in line
    assert "xyz-456" not in line


def test_rendered_exception_text_is_masked() -> None:
    event_dict: EventDict = {
        "event": "SSO login failed",
        "exception": f"Traceback (most recent call last):\nRuntimeError: for url '{IDP_URL_WITH_SECRETS}'",
    }

    masked = mask_personal_data(logger=None, method_name="error", event_dict=event_dict)

    assert masked == {
        "event": "SSO login failed",
        "exception": f"Traceback (most recent call last):\nRuntimeError: for url '{IDP_URL_MASKED}'",
    }


def _api_record(**extra: Any) -> logging.LogRecord:
    record = logging.LogRecord(
        name="prefect.flow_runs",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="user signed in: %(username)s",
        args=({"username": "jane"},),
        exc_info=None,
    )
    record.__dict__.update(extra)
    return record


def test_prefect_api_record_masks_values_of_personal_data_keys() -> None:
    api_handler = APILogHandler()
    add_log_masking_filter(api_handler)
    record = _api_record(password="pw-123", body={"email": "jane@example.com", "branch": "main"})

    assert api_handler.filter(record)
    message = api_handler.format(record)

    assert message == f"user signed in: {MASKED_VALUE}"
    assert record.__dict__["password"] == MASKED_VALUE
    assert record.__dict__["body"] == {"email": MASKED_VALUE, "branch": "main"}


def test_prefect_api_record_with_a_structlog_event_is_masked() -> None:
    api_handler = APILogHandler()
    add_log_masking_filter(api_handler)
    record = logging.LogRecord(
        name="infrahub.tasks",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg={"event": "user signed in", "token": "tok-123"},
        args=(),
        exc_info=None,
    )

    assert api_handler.filter(record)

    assert "tok-123" not in api_handler.format(record)


def test_prefect_api_record_masks_url_query_strings_in_the_message_and_the_exception_text() -> None:
    api_handler = APILogHandler()
    add_log_masking_filter(api_handler)
    error = _exc_info(f"Client error '400 Bad Request' for url '{IDP_URL_WITH_SECRETS}'")
    record = logging.LogRecord(
        name="prefect.flow_runs",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=f"Token request to {IDP_URL_WITH_SECRETS} failed after %s: %r",
        args=(IDP_URL_WITH_SECRETS, error[1]),
        exc_info=error,
    )

    assert api_handler.filter(record)
    message = api_handler.format(record)

    assert message.startswith(
        f"Token request to {IDP_URL_MASKED} failed after {IDP_URL_MASKED}: "
        f"RuntimeError(\"Client error '400 Bad Request' for url '{IDP_URL_MASKED}'\")\nTraceback"
    )
    assert f"RuntimeError: Client error '400 Bad Request' for url '{IDP_URL_MASKED}'" in message
    assert "abc-123" not in message
    assert "xyz-456" not in message


def test_startup_installs_the_masking_filter_on_the_prefect_run_loggers() -> None:
    installed_on = [
        name
        for name in PREFECT_RUN_LOGGERS
        if any(isinstance(log_filter, LogMaskingFilter) for log_filter in logging.getLogger(name).filters)
    ]
    assert installed_on == list(PREFECT_RUN_LOGGERS)


@pytest.fixture
def task_logger_state() -> Iterator[logging.Logger]:
    """Restore the level and the handlers of the task loggers after the worker adds its API handler to them."""
    task_loggers = [logging.getLogger(name) for name in config.SETTINGS.workflow.extra_loggers + DEFAULT_TASK_LOGGERS]
    state_before = {task_logger.name: (task_logger.level, list(task_logger.handlers)) for task_logger in task_loggers}
    try:
        yield task_loggers[-1]
    finally:
        for task_logger in task_loggers:
            level_before, handlers_before = state_before[task_logger.name]
            for handler in list(task_logger.handlers):
                if handler not in handlers_before:
                    task_logger.removeHandler(handler)
            task_logger.setLevel(level_before)


def test_worker_masks_the_records_it_sends_to_the_prefect_api(task_logger_state: logging.Logger) -> None:
    InfrahubWorkerAsync(work_pool_name="test-masking")._init_logger()

    (api_handler,) = [handler for handler in task_logger_state.handlers if isinstance(handler, APILogHandler)]
    record = logging.LogRecord(
        name=task_logger_state.name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg={"event": "flow run step", "access_token": "tok-123"},
        args=(),
        exc_info=None,
    )
    assert api_handler.filter(record)
    assert record.msg == {"event": "flow run step", "access_token": MASKED_VALUE}
