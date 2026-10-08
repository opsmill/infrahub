import ast
import inspect
import textwrap
from dataclasses import dataclass
from uuid import uuid4

import pytest
from infrahub_sdk.branch import BranchData, BranchStatus

from infrahub.core.constants import RepositoryInternalStatus, RepositorySyncStatus, Severity, ValidatorConclusion
from infrahub.core.registry import registry
from infrahub.git import InfrahubRepository
from infrahub.git.tasks import (
    ImportStatusOutcome,
    evaluate_import_status,
    format_check_log_entry,
    resolve_initial_import_branch,
    select_writable_branch_commits,
    warm_up_git_repository,
)


def test_the_warm_up_flow_does_not_tag_its_run_with_the_namespace() -> None:
    """A read starts the warm-up, and the namespace tag is what puts a run in the task list."""
    flow_source = textwrap.dedent(inspect.getsource(warm_up_git_repository.fn))
    add_tags_calls = [
        node
        for node in ast.walk(ast.parse(flow_source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "add_tags"
    ]

    assert [
        {keyword.arg: ast.literal_eval(keyword.value) for keyword in call.keywords if keyword.arg == "namespace"}
        for call in add_tags_calls
    ] == [{"namespace": False}]


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
        default_branch="production",
        has_origin=True,
        cache_repo=None,
        is_read_only=False,
        internal_status=RepositoryInternalStatus.ACTIVE,
        infrahub_branch_name="main",
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


@dataclass(frozen=True, kw_only=True)
class ImportStatusCase:
    name: str
    sync_status: str | None
    internal_status: str


PASSING_IMPORT_STATUS_CASES = [
    ImportStatusCase(
        name="not_written_on_branch", sync_status=None, internal_status=RepositoryInternalStatus.ACTIVE.value
    ),
    ImportStatusCase(
        name="in_sync",
        sync_status=RepositorySyncStatus.IN_SYNC.value,
        internal_status=RepositoryInternalStatus.ACTIVE.value,
    ),
    ImportStatusCase(
        name="syncing",
        sync_status=RepositorySyncStatus.SYNCING.value,
        internal_status=RepositoryInternalStatus.ACTIVE.value,
    ),
    ImportStatusCase(
        name="unknown",
        sync_status=RepositorySyncStatus.UNKNOWN.value,
        internal_status=RepositoryInternalStatus.ACTIVE.value,
    ),
    ImportStatusCase(
        name="inactive_after_import_error",
        sync_status=RepositorySyncStatus.ERROR_IMPORT.value,
        internal_status=RepositoryInternalStatus.INACTIVE.value,
    ),
]


@pytest.mark.parametrize("case", PASSING_IMPORT_STATUS_CASES, ids=[case.name for case in PASSING_IMPORT_STATUS_CASES])
def test_evaluate_import_status_passes_without_import_error(case: ImportStatusCase) -> None:
    outcome = evaluate_import_status(
        sync_status=case.sync_status,
        internal_status=case.internal_status,
        repository_name="dealership-car",
        branch_name="remove-ca",
    )

    assert outcome == ImportStatusOutcome(conclusion=ValidatorConclusion.SUCCESS, severity=Severity.INFO, message="")


@pytest.mark.parametrize(
    "internal_status", [RepositoryInternalStatus.ACTIVE.value, RepositoryInternalStatus.STAGING.value]
)
def test_evaluate_import_status_fails_on_import_error(internal_status: str) -> None:
    outcome = evaluate_import_status(
        sync_status=RepositorySyncStatus.ERROR_IMPORT.value,
        internal_status=internal_status,
        repository_name="dealership-car",
        branch_name="remove-ca",
    )

    assert outcome == ImportStatusOutcome(
        conclusion=ValidatorConclusion.FAILURE,
        severity=Severity.CRITICAL,
        message=(
            "The last import of the objects from repository 'dealership-car' on branch 'remove-ca' failed, so the "
            "objects registered for this repository do not match the content of the branch. Merging would apply "
            "the rest of the branch without them. Review the latest 'Import objects' task for this repository, "
            "resolve the cause and run the checks again."
        ),
    )


def listed_branch(name: str, status: BranchStatus) -> BranchData:
    return BranchData(
        id=f"{name}-id",
        name=name,
        sync_with_git=True,
        is_default=name == "main",
        has_schema_changes=False,
        status=status,
        branched_from="2024-01-01T00:00:00Z",
    )


def test_only_a_branch_that_can_still_record_a_commit_keeps_its_commit() -> None:
    """A branch that rejects a commit would otherwise be selected for one on every sync cycle."""
    statuses = {
        "main": BranchStatus.OPEN,
        "open": BranchStatus.OPEN,
        "upgrade-rebase-needed": BranchStatus.NEED_UPGRADE_REBASE,
        "rebase-needed": BranchStatus.NEED_REBASE,
        "merging": BranchStatus.MERGING,
        "merge-failed": BranchStatus.MERGE_FAILED,
        "merged": BranchStatus.MERGED,
        "deleting": BranchStatus.DELETING,
    }
    branch_commits: dict[str, str | None] = {name: f"commit-{name}" for name in [*statuses, "unlisted"]}
    branches = {name: listed_branch(name=name, status=status) for name, status in statuses.items()}

    assert select_writable_branch_commits(branch_commits=branch_commits, branches=branches) == {
        "main": "commit-main",
        "open": "commit-open",
        "upgrade-rebase-needed": "commit-upgrade-rebase-needed",
    }
