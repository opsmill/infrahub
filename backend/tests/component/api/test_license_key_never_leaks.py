from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub import config
from infrahub.license.models import License, LicenseState, LicenseStatus, NoticeMode
from tests.adapters.license import RecordingLicenseService
from tests.helpers.log import infrahub_log_payloads

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.license.service import LicenseService

LICENSE_KEY = f"leak-sentinel-{uuid4()}"

EXPIRING_LICENSE = License(
    license_id="lic-0042",
    customer_name="Example Networks",
    license_type="commercial",
    product_tier="enterprise",
    support_tier="premium",
    starts_at=datetime(2026, 1, 1, tzinfo=UTC),
    ends_at=datetime(2027, 1, 1, tzinfo=UTC),
    issued_at=datetime(2025, 12, 15, tzinfo=UTC),
    issuer="opsmill-test",
)


@dataclass
class LicenseKeyLeakCase:
    name: str
    replacement_status: LicenseStatus | None
    """Status of an enforcing service swapped in for the community default, which stays in place when None."""

    logged_license_line: tuple[str, str]
    """The event and license state of the one license line the startup logs."""


LICENSE_KEY_LEAK_CASES: list[LicenseKeyLeakCase] = [
    LicenseKeyLeakCase(
        name="community_default",
        replacement_status=None,
        logged_license_line=(
            "A license key is set but ignored, because this deployment does not require a license",
            "not_required",
        ),
    ),
    LicenseKeyLeakCase(
        name="replaced_service_with_an_expiring_license",
        replacement_status=LicenseStatus(state=LicenseState.EXPIRING, license=EXPIRING_LICENSE, days_remaining=12),
        logged_license_line=(
            "License expires soon; set a renewed license in INFRAHUB_LICENSE_KEY on every API server and task worker",
            "expiring",
        ),
    ),
]


@pytest.fixture
def license_key(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(config.SETTINGS.license, "key", LICENSE_KEY)
    return LICENSE_KEY


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in LICENSE_KEY_LEAK_CASES])
async def test_license_key_never_appears_in_the_startup_log_or_the_api_responses(
    db: InfrahubDatabase,
    client: TestClient,
    admin_headers: dict[str, str],
    default_branch: Branch,
    register_core_models_schema: None,
    create_test_admin: Node,
    use_license_service: Callable[[LicenseService], None],
    license_key: str,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    test_case: LicenseKeyLeakCase,
) -> None:
    monkeypatch.setattr(config.SETTINGS.main, "allow_anonymous_access", True)
    if test_case.replacement_status is not None:
        use_license_service(
            RecordingLicenseService(status=test_case.replacement_status, notice_mode=NoticeMode.ENFORCE)
        )

    with caplog.at_level(logging.INFO, logger="infrahub"), client:
        signed_in_info = client.get("/api/info", headers=admin_headers)
        anonymous_info = client.get("/api/info")
        config_response = client.get("/api/config")

    license_lines = [
        (payload["event"], payload["license_state"])
        for payload in infrahub_log_payloads(caplog)
        if "license_state" in payload
    ]
    assert license_lines == [test_case.logged_license_line]
    assert license_key not in caplog.text
    for record in caplog.records:
        assert license_key not in repr(vars(record))

    assert signed_in_info.json()["license"]["state"] == test_case.logged_license_line[1]
    assert anonymous_info.json()["license"] is None
    for response in (signed_in_info, anonymous_info, config_response):
        assert response.status_code == 200
        assert license_key not in response.text
        assert license_key not in repr(response.headers.items())
