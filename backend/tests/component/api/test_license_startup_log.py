from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from infrahub import config
from infrahub.license.models import License, LicenseState, LicenseStatus
from infrahub.workers.dependencies import build_license_service
from tests.adapters.license import RecordingLicenseService
from tests.helpers.dependency_override import override_dependency

if TYPE_CHECKING:
    from fast_depends import Provider
    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

EXPIRED_LICENSE = License(
    license_id="lic-0042",
    customer_name="Example Networks",
    license_type="commercial",
    product_tier="enterprise",
    support_tier="premium",
    starts_at=datetime(2024, 1, 1, tzinfo=UTC),
    ends_at=datetime(2025, 1, 1, tzinfo=UTC),
    issued_at=datetime(2023, 12, 15, tzinfo=UTC),
    issuer="opsmill-test",
)


@dataclass
class StartupLogCase:
    name: str
    license_key: str | None
    replacement_status: LicenseStatus | None
    """Status reported by a service swapped in the way an edition that requires a license registers one."""

    expected: tuple[str, str, str]
    """The level, event and license state of the one license line the startup logs."""


STARTUP_LOG_CASES: list[StartupLogCase] = [
    StartupLogCase(
        name="default_service_without_key",
        license_key=None,
        replacement_status=None,
        expected=("info", "No license is required for this deployment", "not_required"),
    ),
    StartupLogCase(
        name="default_service_with_key",
        license_key="startup-log-license-key",
        replacement_status=None,
        expected=(
            "info",
            "A license key is set but ignored, because this deployment does not require a license",
            "not_required",
        ),
    ),
    StartupLogCase(
        name="replaced_service_reporting_an_expired_license",
        license_key="startup-log-license-key",
        replacement_status=LicenseStatus(state=LicenseState.EXPIRED, license=EXPIRED_LICENSE, days_since_expiry=30),
        expected=(
            "warning",
            "License has expired; set a renewed license in INFRAHUB_LICENSE_KEY on every API server and task worker",
            "expired",
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in STARTUP_LOG_CASES])
async def test_api_server_logs_its_license_state_once_at_startup(
    db: InfrahubDatabase,
    client: TestClient,
    default_branch: Branch,
    register_core_models_schema: None,
    dependency_provider: Provider,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    test_case: StartupLogCase,
) -> None:
    monkeypatch.setattr(config.SETTINGS.license, "key", test_case.license_key)
    replacement: RecordingLicenseService | None = None

    with ExitStack() as stack:
        if test_case.replacement_status is not None:
            replacement = RecordingLicenseService(status=test_case.replacement_status)
            stack.enter_context(
                override_dependency(
                    original=build_license_service,
                    override=lambda: replacement,
                    dependency_provider=dependency_provider,
                )
            )
        stack.enter_context(caplog.at_level("INFO", logger="infrahub"))
        with client:
            pass

    license_lines: list[dict[str, Any]] = [
        record.msg for record in caplog.records if isinstance(record.msg, dict) and "license_state" in record.msg
    ]
    assert [(line["level"], line["event"], line["license_state"]) for line in license_lines] == [test_case.expected]
    if replacement is not None:
        assert replacement.requested_at == [None]
