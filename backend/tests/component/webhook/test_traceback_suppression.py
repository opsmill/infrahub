from __future__ import annotations

import logging

import pytest
from prefect import flow

from infrahub.log import configure_logging
from infrahub.webhook.classifier import ClassifiedFailure, StatusClass, WebhookDeliveryError

CLASSIFIED_MESSAGE = "The target responded with HTTP 404."


@flow(name="raise-classified-failure")
async def _raise_classified_failure() -> None:
    raise WebhookDeliveryError(
        ClassifiedFailure(status_class=StatusClass.HTTP_CLIENT_ERROR, message=CLASSIFIED_MESSAGE)
    )


@flow(name="raise-unclassified-failure")
async def _raise_unclassified_failure() -> None:
    raise RuntimeError("boom")


@pytest.fixture
def configured_logging() -> None:
    # Register the traceback filter on the Prefect run loggers, as production startup does.
    configure_logging(production=False, log_level="DEBUG")


@pytest.mark.usefixtures("configured_logging")
async def test_classified_failure_logs_no_traceback(caplog: pytest.LogCaptureFixture) -> None:
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


@pytest.mark.usefixtures("configured_logging")
async def test_unclassified_failure_logs_a_traceback(caplog: pytest.LogCaptureFixture) -> None:
    with (
        caplog.at_level(logging.INFO, logger="prefect.flow_runs"),
        pytest.raises(RuntimeError, match=r"^boom$"),
    ):
        await _raise_unclassified_failure()

    logged_exceptions = [record.exc_info[1] for record in caplog.records if record.exc_info]
    assert [type(exc) for exc in logged_exceptions] == [RuntimeError]
    assert str(logged_exceptions[0]) == "boom"
