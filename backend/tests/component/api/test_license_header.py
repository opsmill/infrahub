from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from fastapi.templating import Jinja2Templates

from infrahub import config
from infrahub.license.middleware import LICENSE_STATUS_HEADER
from infrahub.license.models import LicenseState, LicenseStatus, NoticeMode
from tests.adapters.license import RecordingLicenseService, build_license_status

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.license.service import LicenseService

EXPIRED = build_license_status(state=LicenseState.EXPIRED)
INFO_QUERY = {"query": "query { InfrahubInfo { version } }"}


@pytest.fixture
def frontend_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve a minimal frontend page, because the backend test environment has no frontend build."""
    (tmp_path / "index.html").write_text("<!doctype html><title>Infrahub</title>")
    monkeypatch.setattr("infrahub.server.templates", Jinja2Templates(directory=tmp_path))


async def test_enforced_license_problem_is_sent_on_rest_and_graphql_responses(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    register_core_models_schema: None,
    create_test_admin: Node,
    use_license_service: Callable[[LicenseService], None],
) -> None:
    use_license_service(RecordingLicenseService(status=EXPIRED, notice_mode=NoticeMode.ENFORCE))

    with client:
        info_response = client.get("/api/info", headers=admin_headers)
        graphql_response = client.post("/graphql", json=INFO_QUERY, headers=admin_headers)

    assert info_response.status_code == 200
    assert info_response.headers.get(LICENSE_STATUS_HEADER) == "expired"
    assert graphql_response.status_code == 200
    assert graphql_response.headers.get(LICENSE_STATUS_HEADER) == "expired"


async def test_enforced_license_problem_is_sent_to_callers_who_are_not_signed_in(
    db: InfrahubDatabase,
    client: TestClient,
    default_branch: Branch,
    register_core_models_schema: None,
    use_license_service: Callable[[LicenseService], None],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rejected request still carries the header, because API-only clients have no other signal."""
    use_license_service(RecordingLicenseService(status=EXPIRED, notice_mode=NoticeMode.ENFORCE))
    monkeypatch.setattr(config.SETTINGS.main, "allow_anonymous_access", False)

    with client:
        response = client.get("/api/info")

    assert response.status_code == 401
    assert response.headers.get(LICENSE_STATUS_HEADER) == "expired"


async def test_enforced_license_problem_is_not_sent_outside_the_api(
    db: InfrahubDatabase,
    client: TestClient,
    default_branch: Branch,
    register_core_models_schema: None,
    use_license_service: Callable[[LicenseService], None],
    frontend_build: None,
) -> None:
    use_license_service(RecordingLicenseService(status=EXPIRED, notice_mode=NoticeMode.ENFORCE))

    with client:
        static_response = client.get("/api-static/swagger-ui.css")
        frontend_response = client.get("/objects/BuiltinTag")

    assert static_response.status_code == 200
    assert LICENSE_STATUS_HEADER not in static_response.headers
    assert frontend_response.status_code == 200
    assert LICENSE_STATUS_HEADER not in frontend_response.headers


@dataclass
class NoHeaderCase:
    name: str
    quiet_mode_status: LicenseStatus | None
    """Status of a quiet-mode service swapped in for the community default, which stays in place when None."""


NO_HEADER_CASES: list[NoHeaderCase] = [
    NoHeaderCase(name="quiet_mode_expired_license", quiet_mode_status=EXPIRED),
    NoHeaderCase(name="community_default", quiet_mode_status=None),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in NO_HEADER_CASES])
async def test_header_is_absent_unless_the_release_enforces_a_license_problem(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    register_core_models_schema: None,
    create_test_admin: Node,
    use_license_service: Callable[[LicenseService], None],
    test_case: NoHeaderCase,
) -> None:
    if test_case.quiet_mode_status is not None:
        use_license_service(RecordingLicenseService(status=test_case.quiet_mode_status, notice_mode=NoticeMode.QUIET))

    with client:
        info_response = client.get("/api/info", headers=admin_headers)
        graphql_response = client.post("/graphql", json=INFO_QUERY, headers=admin_headers)

    assert info_response.status_code == 200
    assert LICENSE_STATUS_HEADER not in info_response.headers
    assert graphql_response.status_code == 200
    assert LICENSE_STATUS_HEADER not in graphql_response.headers
