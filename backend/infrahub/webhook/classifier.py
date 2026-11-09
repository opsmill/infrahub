from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

import httpx

from infrahub.exceptions import HTTPServerError, HTTPServerSSLError, HTTPServerTimeoutError
from infrahub.log import suppress_traceback_in_logs

from .models import WebhookHeaderResolutionError


class StatusClass(StrEnum):
    """Stable, user-facing class of a delivery failure, owning its remediation hint."""

    CONFIG = "CONFIG"
    CONNECTION = "CONNECTION"
    TLS = "TLS"
    TIMEOUT = "TIMEOUT"
    HTTP_CLIENT_ERROR = "HTTP_CLIENT_ERROR"
    HTTP_SERVER_ERROR = "HTTP_SERVER_ERROR"
    UNKNOWN = "UNKNOWN"

    @property
    def remediation(self) -> str:
        match self:
            case StatusClass.CONFIG:
                remediation = "Check the webhook's headers; a configured header value could not be resolved."
            case StatusClass.CONNECTION:
                remediation = "Verify the target endpoint is reachable from Infrahub."
            case StatusClass.TLS:
                remediation = (
                    "Check the endpoint's TLS certificate, or disable certificate validation if that is intended."
                )
            case StatusClass.TIMEOUT:
                remediation = "The target did not respond in time; retry or check the target's responsiveness."
            case StatusClass.HTTP_CLIENT_ERROR:
                remediation = "The target rejected the request; check the URL and authentication."
            case StatusClass.HTTP_SERVER_ERROR:
                remediation = "The target returned a server error; retry, or check the target."
            case StatusClass.UNKNOWN:
                remediation = "An unexpected error occurred during delivery."
            case _:
                assert_never(self)
        return remediation


@dataclass(frozen=True)
class ClassifiedFailure:
    """The settled outcome of a failed delivery: a class and a clean message.

    The remediation hint is read from the class itself, so it cannot drift from it.
    """

    status_class: StatusClass
    message: str

    @property
    def remediation(self) -> str:
        return self.status_class.remediation


@suppress_traceback_in_logs
class WebhookDeliveryError(Exception):
    """A delivery failed with a classified, user-facing reason and no stacktrace.

    Registered so the logging layer drops the raised traceback from the run logs: the failure is an
    expected operational outcome, already reported as a clean classified message, not a crash to debug.
    """

    def __init__(self, failure: ClassifiedFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


EXPECTED_DELIVERY_ERRORS: tuple[type[Exception], ...] = (
    WebhookHeaderResolutionError,
    HTTPServerError,
    httpx.HTTPStatusError,
)
"""Delivery failures with a known, user-facing classification; any other exception is an unexpected crash."""


class WebhookFailureClassifier:
    """Maps a delivery exception to a stable, user-facing failure.

    Pure: the same exception always yields the same classification.
    """

    def classify(self, cause: BaseException) -> ClassifiedFailure:
        match cause:
            case WebhookHeaderResolutionError():
                return ClassifiedFailure(status_class=StatusClass.CONFIG, message=str(cause))
            case HTTPServerSSLError():
                return ClassifiedFailure(status_class=StatusClass.TLS, message=cause.message)
            case HTTPServerTimeoutError():
                return ClassifiedFailure(status_class=StatusClass.TIMEOUT, message=cause.message)
            case HTTPServerError():
                return ClassifiedFailure(status_class=StatusClass.CONNECTION, message=cause.message)
            case httpx.HTTPStatusError():
                response = cause.response
                status_class = (
                    StatusClass.HTTP_SERVER_ERROR if response.is_server_error else StatusClass.HTTP_CLIENT_ERROR
                )
                return ClassifiedFailure(
                    status_class=status_class,
                    message=f"The target responded with HTTP {response.status_code}.",
                )
            case _:
                return ClassifiedFailure(status_class=StatusClass.UNKNOWN, message=str(cause) or "Delivery failed.")
