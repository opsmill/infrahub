from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import httpx

from infrahub.exceptions import HTTPServerError, HTTPServerSSLError, HTTPServerTimeoutError

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
        return _REMEDIATION[self]


_REMEDIATION: dict[StatusClass, str] = {
    StatusClass.CONFIG: "Check the webhook's headers; a configured header value could not be resolved.",
    StatusClass.CONNECTION: "Verify the target endpoint is reachable from Infrahub.",
    StatusClass.TLS: "Check the endpoint's TLS certificate, or disable certificate validation if that is intended.",
    StatusClass.TIMEOUT: "The target did not respond in time; retry or check the target's responsiveness.",
    StatusClass.HTTP_CLIENT_ERROR: "The target rejected the request; check the URL and authentication.",
    StatusClass.HTTP_SERVER_ERROR: "The target returned a server error; retry, or check the target.",
    StatusClass.UNKNOWN: "An unexpected error occurred during delivery.",
}


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


class WebhookDeliveryError(Exception):
    """A delivery failed with a classified, user-facing reason and no stacktrace."""

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
