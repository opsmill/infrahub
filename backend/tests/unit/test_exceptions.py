"""Tests for (un)pickling errors.

Prefect rebuilds errors using pickle.
"""

import pickle  # noqa: S403
from dataclasses import dataclass

import pytest

from infrahub.exceptions import (
    CommitNotFoundError,
    Error,
    GraphQLQueryError,
    MergeRepositoryImportError,
    PropagatedFromWorkerError,
    RepositoryFileNotFoundError,
    RepositoryInvalidBranchError,
    RepositoryPushRejectedError,
    RPCError,
    SchemaNotFoundError,
)
from infrahub.git.models import PushRejectionReason


def _round_trip(error: Error) -> Error:
    return pickle.loads(pickle.dumps(error))  # noqa: S301


class SlottedError(Error):
    """Error subclass that stores state in __slots__ instead of __dict__."""

    __slots__ = ("detail",)

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


@dataclass
class ErrorPickleCase:
    name: str
    error: Error


ERROR_PICKLE_CASES = [
    ErrorPickleCase(
        name="required_kwargs_beyond_message",
        error=SchemaNotFoundError(branch_name="main", identifier="TestingReproSolo"),
    ),
    ErrorPickleCase(
        name="explicit_message_override",
        error=SchemaNotFoundError(branch_name="dev", identifier="CoreNode", message="custom message"),
    ),
    ErrorPickleCase(
        name="multiple_required_positional_args",
        error=RepositoryInvalidBranchError(identifier="repo-1", branch_name="feature", location="/repos/repo-1"),
    ),
    ErrorPickleCase(
        name="repository_file_not_found",
        error=RepositoryFileNotFoundError(repository_name="repo-1", location="/config.yml", commit="abc123"),
    ),
    ErrorPickleCase(
        name="commit_not_found",
        error=CommitNotFoundError(identifier="repo-1", commit="deadbeef"),
    ),
    ErrorPickleCase(
        name="instance_http_code_no_super_init",
        error=PropagatedFromWorkerError(http_code=503, message="worker unavailable"),
    ),
    ErrorPickleCase(
        name="single_message_arg",
        error=RPCError(message="rpc failed"),
    ),
    ErrorPickleCase(
        name="list_arg",
        error=GraphQLQueryError(errors=[{"message": "bad query"}]),
    ),
    ErrorPickleCase(
        name="slotted_state",
        error=SlottedError(detail="slot-value"),
    ),
    ErrorPickleCase(
        name="merge_repository_import",
        error=MergeRepositoryImportError(failed_repositories=["repo-1"], incomplete_repositories=["repo-2"]),
    ),
    ErrorPickleCase(
        name="push_rejection_with_its_reason_and_remote_lines",
        error=RepositoryPushRejectedError(
            identifier="repo-1",
            reason=PushRejectionReason.POLICY,
            remote_message="remote: error: GH006: Protected branch update failed for refs/heads/main.",
            message="Unable to push the branch main to the remote for repository repo-1: [remote rejected]",
        ),
    ),
]


@pytest.mark.parametrize("case", ERROR_PICKLE_CASES, ids=lambda case: case.name)
def test_error_pickle_round_trip(case: ErrorPickleCase) -> None:
    """Every Error subclass round-trips through pickle regardless of signature."""
    restored = _round_trip(case.error)

    assert type(restored) is type(case.error)
    assert restored.__dict__ == case.error.__dict__
    assert restored.args == case.error.args
    assert str(restored) == str(case.error)
    assert restored.HTTP_CODE == case.error.HTTP_CODE


def test_pickle_preserves_extra_constructor_attributes() -> None:
    error = SchemaNotFoundError(branch_name="main", identifier="TestingReproSolo")

    restored = _round_trip(error)

    assert isinstance(restored, SchemaNotFoundError)
    assert restored.branch_name == "main"
    assert restored.identifier == "TestingReproSolo"


def test_pickle_preserves_slot_state() -> None:
    error = SlottedError(detail="slot-value")

    restored = _round_trip(error)

    assert isinstance(restored, SlottedError)
    assert restored.detail == "slot-value"


@dataclass
class MergeRepositoryImportMessageCase:
    name: str
    failed_repositories: list[str]
    incomplete_repositories: list[str]
    expected: str


MERGE_REPOSITORY_IMPORT_MESSAGE_CASES = [
    MergeRepositoryImportMessageCase(
        name="one_failed",
        failed_repositories=["repo-1"],
        incomplete_repositories=[],
        expected=(
            "Cannot merge. The last import of repository 'repo-1' failed: push a fix, reimport the current commit, "
            "or set the repository to inactive."
        ),
    ),
    MergeRepositoryImportMessageCase(
        name="two_failed",
        failed_repositories=["repo-1", "repo-2"],
        incomplete_repositories=[],
        expected=(
            "Cannot merge. The last import of repositories 'repo-1', 'repo-2' failed: push a fix, reimport the "
            "current commit, or set the repositories to inactive."
        ),
    ),
    MergeRepositoryImportMessageCase(
        name="one_incomplete",
        failed_repositories=[],
        incomplete_repositories=["Repo-1"],
        expected=(
            "Cannot merge. Repository 'Repo-1' has not finished importing: wait for the import, or reimport the "
            "current commit if it does not finish."
        ),
    ),
    MergeRepositoryImportMessageCase(
        name="two_incomplete",
        failed_repositories=[],
        incomplete_repositories=["repo-1", "repo-2"],
        expected=(
            "Cannot merge. Repositories 'repo-1', 'repo-2' have not finished importing: wait for the import, or "
            "reimport the current commit if it does not finish."
        ),
    ),
    MergeRepositoryImportMessageCase(
        name="failed_and_incomplete",
        failed_repositories=["repo-1"],
        incomplete_repositories=["repo-2"],
        expected=(
            "Cannot merge. The last import of repository 'repo-1' failed: push a fix, reimport the current commit, "
            "or set the repository to inactive. Repository 'repo-2' has not finished importing: wait for the "
            "import, or reimport the current commit if it does not finish."
        ),
    ),
]


@pytest.mark.parametrize("case", MERGE_REPOSITORY_IMPORT_MESSAGE_CASES, ids=lambda case: case.name)
def test_merge_repository_import_error_names_each_repository(case: MergeRepositoryImportMessageCase) -> None:
    error = MergeRepositoryImportError(
        failed_repositories=case.failed_repositories,
        incomplete_repositories=case.incomplete_repositories,
    )

    assert error.message == case.expected


def test_merge_repository_import_error_requires_a_repository() -> None:
    with pytest.raises(
        ValueError, match=r"^A repository import refusal needs at least one failed or incomplete repository$"
    ):
        MergeRepositoryImportError(failed_repositories=[], incomplete_repositories=[])


def test_reconstructed_error_can_be_raised_and_caught() -> None:
    error = SchemaNotFoundError(branch_name="main", identifier="CoreNode")

    restored = _round_trip(error)

    with pytest.raises(SchemaNotFoundError, match=r"Unable to find the schema CoreNode in the database\."):
        raise restored
