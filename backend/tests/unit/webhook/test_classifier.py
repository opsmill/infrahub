from dataclasses import dataclass

import httpx
import pytest

from infrahub.exceptions import HTTPServerError, HTTPServerSSLError, HTTPServerTimeoutError
from infrahub.webhook.classifier import StatusClass, WebhookFailureClassifier
from infrahub.webhook.models import WebhookHeaderResolutionError


def _status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.test/hook")
    response = httpx.Response(status_code=status_code, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


@dataclass
class ClassifyCase:
    name: str
    cause: BaseException
    expected_class: StatusClass
    expected_message: str
    expected_remediation: str


CLASSIFY_CASES = [
    ClassifyCase(
        name="config",
        cause=WebhookHeaderResolutionError("missing env"),
        expected_class=StatusClass.CONFIG,
        expected_message="missing env",
        expected_remediation="Check the webhook's headers; a configured header value could not be resolved.",
    ),
    ClassifyCase(
        name="tls",
        cause=HTTPServerSSLError(message="bad cert"),
        expected_class=StatusClass.TLS,
        expected_message="bad cert",
        expected_remediation=(
            "Check the endpoint's TLS certificate, or disable certificate validation if that is intended."
        ),
    ),
    ClassifyCase(
        name="timeout",
        cause=HTTPServerTimeoutError(message="timed out"),
        expected_class=StatusClass.TIMEOUT,
        expected_message="timed out",
        expected_remediation="The target did not respond in time; retry or check the target's responsiveness.",
    ),
    ClassifyCase(
        name="connection",
        cause=HTTPServerError(message="unreachable"),
        expected_class=StatusClass.CONNECTION,
        expected_message="unreachable",
        expected_remediation="Verify the target endpoint is reachable from Infrahub.",
    ),
    ClassifyCase(
        name="client_error_404",
        cause=_status_error(404),
        expected_class=StatusClass.HTTP_CLIENT_ERROR,
        expected_message="The target responded with HTTP 404.",
        expected_remediation="The target rejected the request; check the URL and authentication.",
    ),
    ClassifyCase(
        name="client_error_lower_bound_400",
        cause=_status_error(400),
        expected_class=StatusClass.HTTP_CLIENT_ERROR,
        expected_message="The target responded with HTTP 400.",
        expected_remediation="The target rejected the request; check the URL and authentication.",
    ),
    ClassifyCase(
        name="server_error_503",
        cause=_status_error(503),
        expected_class=StatusClass.HTTP_SERVER_ERROR,
        expected_message="The target responded with HTTP 503.",
        expected_remediation="The target returned a server error; retry, or check the target.",
    ),
    ClassifyCase(
        name="server_error_lower_bound_500",
        cause=_status_error(500),
        expected_class=StatusClass.HTTP_SERVER_ERROR,
        expected_message="The target responded with HTTP 500.",
        expected_remediation="The target returned a server error; retry, or check the target.",
    ),
    ClassifyCase(
        name="unknown_with_message",
        cause=ValueError("boom"),
        expected_class=StatusClass.UNKNOWN,
        expected_message="boom",
        expected_remediation="An unexpected error occurred during delivery.",
    ),
    ClassifyCase(
        name="unknown_without_message_falls_back",
        cause=ValueError(),
        expected_class=StatusClass.UNKNOWN,
        expected_message="Delivery failed.",
        expected_remediation="An unexpected error occurred during delivery.",
    ),
]


@pytest.mark.parametrize("case", CLASSIFY_CASES, ids=[case.name for case in CLASSIFY_CASES])
def test_classify(case: ClassifyCase) -> None:
    result = WebhookFailureClassifier().classify(cause=case.cause)

    assert result.status_class is case.expected_class
    assert result.message == case.expected_message
    assert result.remediation == case.expected_remediation


def test_a_more_specific_transport_error_wins_over_its_base() -> None:
    """A subclass of the generic connection error stays distinct from a plain connection failure."""
    assert WebhookFailureClassifier().classify(cause=HTTPServerSSLError(message="x")).status_class is StatusClass.TLS
    assert (
        WebhookFailureClassifier().classify(cause=HTTPServerTimeoutError(message="x")).status_class
        is StatusClass.TIMEOUT
    )
    assert (
        WebhookFailureClassifier().classify(cause=HTTPServerError(message="x")).status_class is StatusClass.CONNECTION
    )


@pytest.mark.parametrize("status_class", list(StatusClass), ids=[member.value for member in StatusClass])
def test_every_status_class_has_a_remediation(status_class: StatusClass) -> None:
    assert status_class.remediation
