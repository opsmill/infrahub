from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.license.reporting import log_license_state
from infrahub.license.service import LicenseServiceUnavailable
from infrahub.workers import dependencies
from infrahub.workers.dependencies import build_license_service, get_license_service
from tests.helpers.dependency_override import override_dependency

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from fast_depends import Provider

    from infrahub.license.service import LicenseService

BUILD_FAILURE_EVENT = (
    "The license service could not be built; reporting the license as invalid with reason internal_error"
)


@pytest.fixture
def empty_singletons() -> Generator[None, None, None]:
    """Start from an empty singleton cache and put the previous entries back, so a cached stand-in cannot leak."""
    saved = dict(dependencies._singletons)
    dependencies._singletons.clear()
    yield
    dependencies._singletons.clear()
    dependencies._singletons.update(saved)


@pytest.fixture
def failing_builds() -> tuple[list[None], Callable[[], LicenseService]]:
    builds: list[None] = []

    def build() -> LicenseService:
        builds.append(None)
        raise RuntimeError("license key verification failed")

    return builds, build


def _infrahub_payloads(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    return [record.msg for record in caplog.records if record.name == "infrahub" and isinstance(record.msg, dict)]


def test_get_license_service_stands_in_once_for_a_service_that_cannot_be_built(
    empty_singletons: None,
    failing_builds: tuple[list[None], Callable[[], LicenseService]],
    dependency_provider: Provider,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The failed build is logged once and not retried, so a broken builder costs one traceback, not one per read."""
    builds, build = failing_builds

    with (
        override_dependency(original=build_license_service, override=build, dependency_provider=dependency_provider),
        caplog.at_level("INFO", logger="infrahub"),
    ):
        first = get_license_service()
        second = get_license_service()

    assert isinstance(first, LicenseServiceUnavailable)
    assert second is first
    assert len(builds) == 1
    assert [(payload["level"], payload["event"], payload["exc_info"]) for payload in _infrahub_payloads(caplog)] == [
        ("error", BUILD_FAILURE_EVENT, True)
    ]


def test_startup_license_line_reports_a_service_that_cannot_be_built_as_invalid(
    empty_singletons: None,
    failing_builds: tuple[list[None], Callable[[], LicenseService]],
    dependency_provider: Provider,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _, build = failing_builds

    with (
        override_dependency(original=build_license_service, override=build, dependency_provider=dependency_provider),
        caplog.at_level("INFO", logger="infrahub"),
    ):
        log_license_state(service=get_license_service(), key_is_set=True)

    build_failure, state_line = _infrahub_payloads(caplog)
    assert (build_failure["level"], build_failure["event"]) == ("error", BUILD_FAILURE_EVENT)
    assert {name: value for name, value in state_line.items() if name != "timestamp"} == {
        "event": "License state could not be determined because of an internal error; see the error logged before",
        "level": "error",
        "logger": "infrahub",
        "license_state": "invalid",
        "license_reason": "internal_error",
    }
