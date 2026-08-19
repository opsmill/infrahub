from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
import pytest
from prefect import flow, task

from infrahub.log import PREFECT_RUN_LOGGERS, install_traceback_suppression_filter
from infrahub.webhook.classifier import (
    EXPECTED_DELIVERY_ERRORS,
    ClassifiedFailure,
    StatusClass,
    WebhookDeliveryError,
    WebhookFailureClassifier,
)

if TYPE_CHECKING:
    from collections.abc import Generator

CLASSIFIED_MESSAGE = "The target responded with HTTP 404."


@flow(name="raise-classified-failure")
async def _raise_classified_failure() -> None:
    raise WebhookDeliveryError(
        ClassifiedFailure(status_class=StatusClass.HTTP_CLIENT_ERROR, message=CLASSIFIED_MESSAGE)
    )


@flow(name="raise-unclassified-failure")
async def _raise_unclassified_failure() -> None:
    raise RuntimeError("boom")


@task(name="classify-transport-failure")
async def _classify_transport_failure() -> None:
    # Mirror the delivery task: an expected transport error becomes a classified delivery error.
    request = httpx.Request("POST", "https://example.test/hook")
    try:
        raise httpx.HTTPStatusError("404", request=request, response=httpx.Response(404, request=request))
    except EXPECTED_DELIVERY_ERRORS as cause:
        raise WebhookDeliveryError(WebhookFailureClassifier().classify(cause=cause)) from None


@flow(name="send-classifying-in-task")
async def _send_classifying_in_task() -> None:
    await _classify_transport_failure()


@pytest.fixture
def traceback_suppression_installed() -> Generator[None, None, None]:
    """Register the traceback filter on the Prefect run loggers, as production startup does, then remove it.

    Only the filter is installed, not the whole of configure_logging: that startup routine also raises
    the root log level, replaces the root handler and reconfigures structlog, none of which these
    assertions need and none of which it undoes. Called from a fixture it would leak that state into
    every test that follows in the same worker — overriding the WARNING root level the suite pins in
    pytest_configure, so unrelated tests drown in DEBUG records from the database driver and the HTTP
    client.
    """
    traceback_filter = install_traceback_suppression_filter()
    yield
    for prefect_logger_name in PREFECT_RUN_LOGGERS:
        logging.getLogger(prefect_logger_name).removeFilter(traceback_filter)


async def test_classified_failure_logs_no_traceback(
    traceback_suppression_installed: None, caplog: pytest.LogCaptureFixture
) -> None:
    with (
        caplog.at_level(logging.INFO, logger="prefect.flow_runs"),
        pytest.raises(WebhookDeliveryError, match=r"^The target responded with HTTP 404\.$"),
    ):
        await _raise_classified_failure()

    # The traceback-bearing record is dropped, so nothing the logger emits carries an exception...
    assert [record for record in caplog.records if record.exc_info] == []
    # ...while the classified reason still surfaces (wrapped in Prefect's own state summary, so the
    # owned reason is matched as a substring rather than pinning Prefect's phrasing).
    assert CLASSIFIED_MESSAGE in caplog.text


async def test_classified_failure_from_task_logs_no_traceback(
    traceback_suppression_installed: None, caplog: pytest.LogCaptureFixture
) -> None:
    # The transport error is caught and classified inside the task, so the failure the engine records
    # for the task run is a delivery error whose traceback is dropped — not the raw transport stacktrace.
    with (
        caplog.at_level(logging.INFO, logger="prefect.task_runs"),
        caplog.at_level(logging.INFO, logger="prefect.flow_runs"),
        pytest.raises(WebhookDeliveryError, match=r"^The target responded with HTTP 404\.$"),
    ):
        await _send_classifying_in_task()

    # Neither the task run nor the flow run leaks a traceback-bearing record...
    assert [record for record in caplog.records if record.exc_info] == []
    # ...while the classified reason still surfaces.
    assert CLASSIFIED_MESSAGE in caplog.text


async def test_unclassified_failure_logs_a_traceback(
    traceback_suppression_installed: None, caplog: pytest.LogCaptureFixture
) -> None:
    with (
        caplog.at_level(logging.INFO, logger="prefect.flow_runs"),
        pytest.raises(RuntimeError, match=r"^boom$"),
    ):
        await _raise_unclassified_failure()

    logged_exceptions = [record.exc_info[1] for record in caplog.records if record.exc_info]
    assert [type(exc) for exc in logged_exceptions] == [RuntimeError]
    assert str(logged_exceptions[0]) == "boom"
