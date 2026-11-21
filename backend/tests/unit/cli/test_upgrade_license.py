from __future__ import annotations

import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest
import typer

from infrahub import config
from infrahub.cli import upgrade
from infrahub.cli.upgrade import _print_license_section, _upgrade_check, _upgrade_execute, console
from infrahub.license.models import License, LicenseFailureReason, LicenseState, LicenseStatus, NoticeMode
from infrahub.license.service import LicenseServiceCommunity
from infrahub.workers.dependencies import build_license_service
from tests.adapters.license import FailingLicenseService, FailingNoticeModeLicenseService, RecordingLicenseService
from tests.helpers.dependency_override import override_dependency
from tests.helpers.log import infrahub_log_payloads

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Coroutine, Iterator

    from fast_depends import Provider

    from infrahub.database import InfrahubDatabase
    from infrahub.license.service import LicenseService

ANSI_STYLE = re.compile(r"\x1b\[[0-9;]*m")
LOG_TIME = re.compile(r"^\[[^\]]+\]")
LOG_TIMES = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]", re.MULTILINE)
UNLICENSED_SECTION = (
    "License: not set Set INFRAHUB_LICENSE_KEY on the servers and task workers. "
    "From Infrahub 1.13, every user sees an Unlicensed banner without it."
)

LICENSE = License(
    license_id="lic-0042",
    customer_name="ACME [emea] Ltd",
    license_type="commercial",
    product_tier="enterprise",
    support_tier="premium",
    starts_at=datetime(2026, 10, 1, tzinfo=UTC),
    ends_at=datetime(2027, 10, 1, tzinfo=UTC),
    issued_at=datetime(2026, 9, 15, tzinfo=UTC),
    issuer="opsmill-test",
)


def _printed_words(service: LicenseService) -> str:
    """Return what the section printed with the log time, styling and line wrapping removed."""
    with console.capture() as capture:
        _print_license_section(service=service)
    return " ".join(LOG_TIME.sub("", ANSI_STYLE.sub("", capture.get())).split())


def _words(lines: list[str]) -> str:
    return " ".join(" ".join(lines).split())


def test_print_license_section_prints_the_report_through_the_migration_console() -> None:
    service = RecordingLicenseService(
        status=LicenseStatus(state=LicenseState.UNLICENSED), notice_mode=NoticeMode.QUIET, enforcing_release="1.13"
    )

    assert _printed_words(service=service) == _words(
        [
            "License: not set",
            "  Set INFRAHUB_LICENSE_KEY on the servers and task workers.",
            "  From Infrahub 1.13, every user sees an Unlicensed banner without it.",
        ]
    )


def test_print_license_section_prints_the_customer_name_verbatim() -> None:
    service = RecordingLicenseService(
        status=LicenseStatus(state=LicenseState.VALID, license=LICENSE, days_remaining=200)
    )

    assert _printed_words(service=service) == "License: ACME [emea] Ltd, commercial, ends 2027-09-30"


def test_print_license_section_prints_nothing_when_no_license_is_required() -> None:
    with console.capture() as capture:
        _print_license_section(service=RecordingLicenseService(status=LicenseStatus(state=LicenseState.NOT_REQUIRED)))

    assert not capture.get()


def test_print_license_section_logs_and_skips_a_section_that_cannot_be_built(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = FailingNoticeModeLicenseService(status=LicenseStatus(state=LicenseState.UNLICENSED))

    with caplog.at_level("INFO", logger="infrahub"), console.capture() as capture:
        _print_license_section(service=service)

    assert not capture.get()
    assert [(payload["level"], payload["event"], payload["exc_info"]) for payload in infrahub_log_payloads(caplog)] == [
        ("error", "The license section of the upgrade output could not be built; skipping it", True)
    ]


LICENSE_KEY = f"leak-sentinel-{uuid4()}"


@dataclass
class LicenseKeyLeakCase:
    name: str
    service: LicenseService
    printed: str
    """What the section prints, with the log time, styling and line wrapping removed."""


LICENSE_KEY_LEAK_CASES: list[LicenseKeyLeakCase] = [
    LicenseKeyLeakCase(name="community_default", service=LicenseServiceCommunity(), printed=""),
    LicenseKeyLeakCase(
        name="enforcing_service_with_an_expiring_license",
        service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.EXPIRING, license=LICENSE, days_remaining=12),
            notice_mode=NoticeMode.ENFORCE,
        ),
        printed="License: ACME [emea] Ltd, commercial, expires in 12 days (2027-09-30)",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in LICENSE_KEY_LEAK_CASES])
def test_print_license_section_never_prints_the_license_key(
    test_case: LicenseKeyLeakCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config.SETTINGS.license, "key", LICENSE_KEY)

    printed = _printed_words(service=test_case.service)

    assert printed == test_case.printed
    assert LICENSE_KEY not in printed


def test_print_license_section_reports_a_failing_status_read_as_an_internal_error() -> None:
    assert _printed_words(service=FailingLicenseService()) == (
        "License: could not be determined because of an internal error. Check the server logs."
    )


@dataclass
class PromptCase:
    name: str
    service: LicenseService


PROMPT_CASES: list[PromptCase] = [
    PromptCase(
        name="not_required", service=RecordingLicenseService(status=LicenseStatus(state=LicenseState.NOT_REQUIRED))
    ),
    PromptCase(name="unlicensed", service=RecordingLicenseService(status=LicenseStatus(state=LicenseState.UNLICENSED))),
    PromptCase(
        name="unlicensed_enforced",
        service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.UNLICENSED), notice_mode=NoticeMode.ENFORCE
        ),
    ),
    PromptCase(
        name="invalid_enforced",
        service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.INVALID, reason=LicenseFailureReason.BAD_SIGNATURE),
            notice_mode=NoticeMode.ENFORCE,
        ),
    ),
    PromptCase(
        name="expired_enforced",
        service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.EXPIRED, license=LICENSE, days_since_expiry=4),
            notice_mode=NoticeMode.ENFORCE,
        ),
    ),
    PromptCase(
        name="not_yet_valid_enforced",
        service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.NOT_YET_VALID, license=LICENSE, days_remaining=400),
            notice_mode=NoticeMode.ENFORCE,
        ),
    ),
    PromptCase(
        name="expiring",
        service=RecordingLicenseService(
            status=LicenseStatus(state=LicenseState.EXPIRING, license=LICENSE, days_remaining=12)
        ),
    ),
    PromptCase(name="failing_status", service=FailingLicenseService(notice_mode=NoticeMode.ENFORCE)),
    PromptCase(
        name="failing_notice_mode",
        service=FailingNoticeModeLicenseService(status=LicenseStatus(state=LicenseState.UNLICENSED)),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PROMPT_CASES])
def test_print_license_section_never_prompts_and_returns_normally(
    test_case: PromptCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The upgrade runs unattended, so no license state may prompt, stop it or change its exit code."""
    prompts: list[str] = []

    def record_prompt(text: str, *args: object, **kwargs: object) -> bool:
        prompts.append(text)
        return False

    monkeypatch.setattr(typer, "confirm", record_prompt)

    with console.capture():
        _print_license_section(service=test_case.service)

    assert prompts == []


def _returning(value: Any) -> Callable[..., Coroutine[Any, Any, Any]]:
    async def step(*args: Any, **kwargs: Any) -> Any:
        return value

    return step


@asynccontextmanager
async def _task_manager_client(*args: Any, **kwargs: Any) -> AsyncIterator[None]:
    yield None


@pytest.fixture
def upgrade_steps_with_nothing_to_do(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the database and task manager steps, which the place of the license section does not depend on."""
    for name, value in (
        ("detect_migration_to_run", []),
        ("migrate_database", True),
        ("initialize_internal_schema", None),
        ("update_core_schema", None),
        ("check_core_schema_diff", False),
        ("upgrade_menu", None),
        ("upgrade_permissions", None),
        ("setup_blocks", None),
        ("setup_worker_pools", None),
        ("setup_deployments", None),
        ("trigger_configure_all", None),
        ("mark_branches_needing_rebase", []),
        ("get_branches_needing_rebase", []),
    ):
        monkeypatch.setattr(upgrade, name, _returning(value))
    monkeypatch.setattr(upgrade, "get_client", _task_manager_client)


@pytest.fixture
def unlicensed_service(dependency_provider: Provider) -> Iterator[None]:
    service = RecordingLicenseService(
        status=LicenseStatus(state=LicenseState.UNLICENSED), notice_mode=NoticeMode.QUIET, enforcing_release="1.13"
    )
    with override_dependency(
        original=build_license_service, override=lambda: service, dependency_provider=dependency_provider
    ):
        yield


def _printed_output_words(printed: str) -> str:
    return " ".join(LOG_TIMES.sub("", ANSI_STYLE.sub("", printed)).split())


@pytest.mark.usefixtures("upgrade_steps_with_nothing_to_do", "unlicensed_service")
async def test_upgrade_check_prints_the_license_section_before_the_closing_line() -> None:
    db = cast("InfrahubDatabase", object())

    with console.capture() as capture:
        await _upgrade_check(db=db, root_node_graph_version=1)

    assert _printed_output_words(capture.get()) == (
        "Infrahub Upgrade Check Database: Reachable: yes Database migrations: Up to date, nothing to do "
        "Core schema: Up to date, nothing to do Branches: No branches need rebase "
        f"{UNLICENSED_SECTION} Run 'infrahub upgrade' to apply all changes."
    )


@pytest.mark.usefixtures("upgrade_steps_with_nothing_to_do", "unlicensed_service")
async def test_upgrade_prints_the_license_section_after_the_upgrade_completes() -> None:
    db = cast("InfrahubDatabase", object())

    with console.capture() as capture:
        await _upgrade_execute(db=db, root_node_graph_version=1)

    assert _printed_output_words(capture.get()) == (
        "Step 1/6: Database migrations Step 2/6: Internal schema Internal schema initialized "
        "Step 3/6: Core schema Step 4/6: Internal objects Step 5/6: Task manager Task manager configured "
        "Step 6/6: Branch rebase Found 0 branches that need to be rebased Upgrade complete SUCCESS "
        f"{UNLICENSED_SECTION}"
    )
