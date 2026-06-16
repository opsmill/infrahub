from dataclasses import dataclass
from uuid import uuid4

import pytest

from infrahub.core.constants import RepositoryInternalStatus
from infrahub.core.registry import registry
from infrahub.git import InfrahubRepository
from infrahub.git.tasks import format_check_log_entry, resolve_initial_import_branch


@dataclass
class ImportBranchCase:
    name: str
    init_failed: bool
    reinitialized: bool
    expected: str | None


IMPORT_BRANCH_CASES = [
    # A fresh clone (init raised, recreated via new) must seed its git default branch.
    ImportBranchCase(name="freshly_created", init_failed=True, reinitialized=False, expected="production"),
    # A re-cloned local copy (local directory was missing) must seed its git default branch.
    ImportBranchCase(name="reinitialized", init_failed=False, reinitialized=True, expected="production"),
    # An already-present valid clone needs no initial import.
    ImportBranchCase(name="existing_clone", init_failed=False, reinitialized=False, expected=None),
]


@pytest.mark.parametrize("case", IMPORT_BRANCH_CASES, ids=[case.name for case in IMPORT_BRANCH_CASES])
def test_resolve_initial_import_branch_uses_git_default(
    case: ImportBranchCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The seeded branch must be the repository's git default branch, never the platform default."""
    monkeypatch.setattr(registry, "_default_branch", "main")
    # The repository's git default branch ("production") differs from Infrahub's default ("main").
    assert registry.default_branch != "production"
    repo = InfrahubRepository(
        id=uuid4(),
        name="test-repository",
        location="git@github.com:mock/test-repository.git",
        default_branch_name="production",
        has_origin=True,
        cache_repo=None,
        is_read_only=False,
        internal_status=RepositoryInternalStatus.ACTIVE.value,
        infrahub_branch_name=None,
        reinitialized=case.reinitialized,
    )

    assert resolve_initial_import_branch(repo, init_failed=case.init_failed) == case.expected


def test_format_check_log_entry_message_only() -> None:
    entry = {"level": "ERROR", "message": "boom", "branch": "main"}

    assert format_check_log_entry(entry) == "[ERROR] boom"


def test_format_check_log_entry_with_object_type_and_id() -> None:
    entry = {
        "level": "ERROR",
        "message": "Duplicate serial '12345' for manufacturer 'Acme'.",
        "branch": "main",
        "object_id": "abc-123",
        "object_type": "DcimDeviceAsset",
    }

    assert format_check_log_entry(entry) == (
        "[ERROR] Duplicate serial '12345' for manufacturer 'Acme'. (object_type=DcimDeviceAsset, object_id=abc-123)"
    )


def test_format_check_log_entry_with_object_id_only() -> None:
    entry = {
        "level": "INFO",
        "message": "validated",
        "branch": "main",
        "object_id": "abc-123",
    }

    assert format_check_log_entry(entry) == "[INFO] validated (object_id=abc-123)"


def test_format_check_log_entry_with_object_type_only() -> None:
    entry = {
        "level": "ERROR",
        "message": "missing description",
        "branch": "main",
        "object_type": "TestingCar",
    }

    assert format_check_log_entry(entry) == "[ERROR] missing description (object_type=TestingCar)"


def test_format_check_log_entry_produces_single_line_per_entry() -> None:
    """Regression: the formatter must emit exactly one line per log record."""
    entry = {
        "level": "ERROR",
        "message": "multi word message",
        "branch": "main",
        "object_id": "abc",
        "object_type": "Foo",
    }

    rendered = format_check_log_entry(entry)

    assert "\n" not in rendered
    assert rendered.count("[ERROR]") == 1
