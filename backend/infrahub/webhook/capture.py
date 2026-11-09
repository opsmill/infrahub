from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from .constants import RESPONSE_BODY_CAPTURE_LIMIT

if TYPE_CHECKING:
    from .classifier import ClassifiedFailure


class CapturedRequest(BaseModel):
    url: str
    headers: dict[str, Any]


class CapturedResponse(BaseModel):
    status_code: int | None = None
    body: str | None = None
    latency_ms: float | None = None


class CapturedError(BaseModel):
    status_class: str
    message: str
    remediation: str


class CapturedHttp(BaseModel):
    """The request, response, and classified error a delivery attempt exchanged.

    Serialized as the delivery's `http` artifact and projected back onto the task's
    `http_request` / `http_response` / `error` fields. Headers are redacted before capture,
    so no raw secret is ever persisted.
    """

    request: CapturedRequest
    response: CapturedResponse | None = None
    error: CapturedError | None = None

    def to_artifact_data(self) -> dict[str, Any]:
        return self.model_dump()


def _truncate_body(body: str | None) -> str | None:
    if body is not None and len(body) > RESPONSE_BODY_CAPTURE_LIMIT:
        return body[:RESPONSE_BODY_CAPTURE_LIMIT]
    return body


def build_http_capture(
    *,
    url: str,
    redacted_headers: dict[str, Any],
    status_code: int | None = None,
    body: str | None = None,
    latency_ms: float | None = None,
    failure: ClassifiedFailure | None = None,
) -> CapturedHttp:
    """Assemble a capture from the pieces available for one delivery attempt.

    A response block is recorded only when the target answered (a status code is known); an error
    block only when the attempt was classified as failed. The headers must already be redacted.
    """
    response = None
    if status_code is not None:
        response = CapturedResponse(status_code=status_code, body=_truncate_body(body), latency_ms=latency_ms)
    error = None
    if failure is not None:
        error = CapturedError(
            status_class=str(failure.status_class), message=failure.message, remediation=failure.remediation
        )
    return CapturedHttp(request=CapturedRequest(url=url, headers=redacted_headers), response=response, error=error)
