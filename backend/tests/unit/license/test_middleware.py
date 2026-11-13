from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from infrahub.license.middleware import LICENSE_STATUS_HEADER, LicenseStatusHeaderMiddleware
from infrahub.license.models import LicenseFailureReason, LicenseState, LicenseStatus, NoticeMode
from tests.adapters.license import (
    FailingLicenseService,
    FailingNoticeModeLicenseService,
    RecordingLicenseService,
    build_license_status,
)
from tests.helpers.log import find_logged_events

if TYPE_CHECKING:
    from starlette.requests import Request

    from infrahub.license.service import LicenseService

EXPIRED = build_license_status(state=LicenseState.EXPIRED)


async def _ok(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def _not_found(request: Request) -> PlainTextResponse:
    raise HTTPException(status_code=404)


def _client(service: LicenseService) -> TestClient:
    app = Starlette(
        routes=[Route("/api/missing", _not_found), Route("/{path:path}", _ok)],
        middleware=[Middleware(LicenseStatusHeaderMiddleware, license_service_provider=lambda: service)],
    )
    return TestClient(app)


@dataclass
class HeaderCase:
    name: str
    status: LicenseStatus
    notice_mode: NoticeMode
    expected: str | None


HEADER_CASES: list[HeaderCase] = [
    HeaderCase(name="enforce_expired", status=EXPIRED, notice_mode=NoticeMode.ENFORCE, expected="expired"),
    HeaderCase(
        name="enforce_expiring",
        status=build_license_status(state=LicenseState.EXPIRING),
        notice_mode=NoticeMode.ENFORCE,
        expected="expiring",
    ),
    HeaderCase(
        name="enforce_invalid_signature",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.BAD_SIGNATURE),
        notice_mode=NoticeMode.ENFORCE,
        expected="invalid",
    ),
    HeaderCase(
        name="enforce_valid",
        status=build_license_status(state=LicenseState.VALID),
        notice_mode=NoticeMode.ENFORCE,
        expected=None,
    ),
    HeaderCase(
        name="enforce_not_required",
        status=LicenseStatus(state=LicenseState.NOT_REQUIRED),
        notice_mode=NoticeMode.ENFORCE,
        expected=None,
    ),
    HeaderCase(
        name="enforce_invalid_internal_error",
        status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.INTERNAL_ERROR),
        notice_mode=NoticeMode.ENFORCE,
        expected=None,
    ),
    HeaderCase(name="quiet_expired", status=EXPIRED, notice_mode=NoticeMode.QUIET, expected=None),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in HEADER_CASES])
def test_header_carries_the_state_only_when_the_notice_asks_for_it(test_case: HeaderCase) -> None:
    service = RecordingLicenseService(status=test_case.status, notice_mode=test_case.notice_mode)

    with _client(service=service) as client:
        response = client.get("/api/x")

    assert response.status_code == 200
    assert response.headers.get(LICENSE_STATUS_HEADER) == test_case.expected


@pytest.mark.parametrize("path", ["/api", "/api/x", "/graphql", "/graphql/x"])
def test_header_is_sent_on_rest_and_graphql_paths(path: str) -> None:
    service = RecordingLicenseService(status=EXPIRED, notice_mode=NoticeMode.ENFORCE)

    with _client(service=service) as client:
        response = client.get(path)

    assert response.headers.get(LICENSE_STATUS_HEADER) == "expired"


@pytest.mark.parametrize("path", ["/api-static/x", "/assets/x", "/docs/x", "/"])
def test_header_is_never_sent_outside_rest_and_graphql_paths(path: str) -> None:
    service = RecordingLicenseService(status=EXPIRED, notice_mode=NoticeMode.ENFORCE)

    with _client(service=service) as client:
        response = client.get(path)

    assert response.status_code == 200
    assert LICENSE_STATUS_HEADER not in response.headers


def test_header_is_sent_on_error_responses() -> None:
    service = RecordingLicenseService(status=EXPIRED, notice_mode=NoticeMode.ENFORCE)

    with _client(service=service) as client:
        response = client.get("/api/missing")

    assert response.status_code == 404
    assert response.headers.get(LICENSE_STATUS_HEADER) == "expired"


@dataclass
class FailureCase:
    name: str
    service: LicenseService
    event: str


FAILURE_CASES: list[FailureCase] = [
    FailureCase(
        name="status_raises",
        service=FailingLicenseService(notice_mode=NoticeMode.ENFORCE),
        event="The license service failed; reporting the license as invalid with reason internal_error",
    ),
    FailureCase(
        name="notice_mode_raises",
        service=FailingNoticeModeLicenseService(status=EXPIRED),
        event="The license status header could not be computed; sending the response without it",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FAILURE_CASES])
def test_failing_license_service_leaves_responses_untouched_and_is_logged_once(
    test_case: FailureCase, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("ERROR", logger="infrahub"), _client(service=test_case.service) as client:
        responses = [client.get("/api/x") for _ in range(2)]

    assert [(response.status_code, response.text) for response in responses] == [(200, "ok"), (200, "ok")]
    assert [LICENSE_STATUS_HEADER in response.headers for response in responses] == [False, False]
    failures = find_logged_events(caplog, event=test_case.event)
    assert [(failure["level"], failure["exc_info"]) for failure in failures] == [("error", True)]
