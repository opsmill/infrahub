"""Tests for (un)pickling errors, and for the errors whose traceback the Prefect run logs drop.

Prefect rebuilds errors using pickle.
"""

import logging
import pickle  # noqa: S403
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest

from infrahub.core.validators.model import SchemaViolation
from infrahub.exceptions import (
    CommitNotFoundError,
    Error,
    GraphQLQueryError,
    MergeConflictsUnresolvedError,
    MergeConstraintsViolatedError,
    MergeRefusedError,
    MergeRepositoryImportError,
    PropagatedFromWorkerError,
    RepositoryCredentialsRefusedError,
    RepositoryFileNotFoundError,
    RepositoryInvalidBranchError,
    RepositoryNotSynchronizedError,
    RepositoryPushRejectedError,
    RPCError,
    SchemaNotFoundError,
    ValidationError,
)
from infrahub.git.models import PushRejectionReason
from infrahub.log import _TRACEBACK_SUPPRESSED_TYPES, TracebackSuppressionFilter


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
        error=MergeRepositoryImportError(
            failed_repositories=["repo-1"],
            incomplete_repositories=["repo-2"],
            ref_missing_repositories={"repo-3": "v1.0"},
        ),
    ),
    ErrorPickleCase(
        name="merge_refused",
        error=MergeRefusedError("Cannot merge a branch while a merge is in progress."),
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
    ref_missing_repositories: dict[str, str | None] = field(default_factory=dict)


MERGE_REPOSITORY_IMPORT_MESSAGE_CASES = [
    MergeRepositoryImportMessageCase(
        name="one_ref_missing",
        failed_repositories=[],
        incomplete_repositories=[],
        ref_missing_repositories={"repo-1": "v1.0"},
        expected=(
            "Cannot merge. The tracked ref 'v1.0' of repository 'repo-1' was missing from the remote when last "
            "checked: restore the ref or edit the ref of the repository, then reimport the current commit."
        ),
    ),
    MergeRepositoryImportMessageCase(
        name="one_ref_missing_with_an_unknown_ref",
        failed_repositories=[],
        incomplete_repositories=[],
        ref_missing_repositories={"repo-1": None},
        expected=(
            "Cannot merge. The tracked ref of repository 'repo-1' was missing from the remote when last checked: "
            "restore the ref or edit the ref of the repository, then reimport the current commit."
        ),
    ),
    MergeRepositoryImportMessageCase(
        name="two_ref_missing_sorted_by_repository",
        failed_repositories=[],
        incomplete_repositories=[],
        ref_missing_repositories={"repo-2": "release", "repo-1": "v1.0"},
        expected=(
            "Cannot merge. The tracked ref 'v1.0' of repository 'repo-1', ref 'release' of repository 'repo-2' were "
            "missing from the remote when last checked: restore the ref or edit the ref of the repositories, then "
            "reimport the current commit."
        ),
    ),
    MergeRepositoryImportMessageCase(
        name="failed_and_ref_missing",
        failed_repositories=["repo-1"],
        incomplete_repositories=[],
        ref_missing_repositories={"repo-2": "v1.0"},
        expected=(
            "Cannot merge. The last import of repository 'repo-1' failed: push a fix, reimport the current commit, "
            "or set the repository to inactive. The tracked ref 'v1.0' of repository 'repo-2' was missing from the "
            "remote when last checked: restore the ref or edit the ref of the repository, then reimport the current "
            "commit."
        ),
    ),
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
        ref_missing_repositories=case.ref_missing_repositories,
    )

    assert error.message == case.expected


def test_merge_repository_import_error_requires_a_repository() -> None:
    with pytest.raises(
        ValueError,
        match=r"^A repository import refusal needs at least one failed, incomplete or ref-missing repository$",
    ):
        MergeRepositoryImportError(failed_repositories=[], incomplete_repositories=[], ref_missing_repositories={})


def test_reconstructed_error_can_be_raised_and_caught() -> None:
    error = SchemaNotFoundError(branch_name="main", identifier="CoreNode")

    restored = _round_trip(error)

    with pytest.raises(SchemaNotFoundError, match=r"Unable to find the schema CoreNode in the database\."):
        raise restored


@dataclass
class MergeRefusalCase:
    name: str
    build: Callable[[], ValidationError]


MERGE_REFUSAL_CASES = [
    MergeRefusalCase(
        name="refused",
        build=lambda: MergeRefusedError("Cannot merge a branch while a merge is in progress."),
    ),
    MergeRefusalCase(
        name="repository_import_failed",
        build=lambda: MergeRepositoryImportError(
            failed_repositories=["blue"], incomplete_repositories=[], ref_missing_repositories={}
        ),
    ),
    MergeRefusalCase(
        name="repository_not_synchronized",
        build=lambda: RepositoryNotSynchronizedError("Unable to merge branch branch-c, a remote head is not imported."),
    ),
    MergeRefusalCase(
        name="repository_credentials_refused",
        build=lambda: RepositoryCredentialsRefusedError("Unable to merge branch branch-c, fix the credentials."),
    ),
    MergeRefusalCase(
        name="conflicts_unresolved",
        build=lambda: MergeConflictsUnresolvedError(conflict_paths=["data/TestCar/name"], branch_name="branch-c"),
    ),
    MergeRefusalCase(
        name="constraints_violated",
        build=lambda: MergeConstraintsViolatedError(
            violations=[
                SchemaViolation(
                    node_id="car-1",
                    node_kind="TestCar",
                    display_label="volt",
                    full_display_label="TestCar volt",
                    message="TestCar volt violates the uniqueness constraint on name.",
                )
            ],
            schema_conflicts=[],
        ),
    ),
]


def _flow_run_record(exception: BaseException) -> logging.LogRecord:
    return logging.LogRecord(
        name="prefect.flow_runs",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Encountered exception during execution: %r",
        args=(exception,),
        exc_info=(type(exception), exception, exception.__traceback__),
    )


@pytest.mark.parametrize("case", MERGE_REFUSAL_CASES, ids=lambda case: case.name)
def test_merge_refusal_drops_its_traceback_record(case: MergeRefusalCase) -> None:
    """A parent flow re-raises the refusal of its subflow after unpickling it, so the rebuilt error is checked too."""
    refusal = case.build()
    suppression_filter = TracebackSuppressionFilter(_TRACEBACK_SUPPRESSED_TYPES)

    assert suppression_filter.filter(_flow_run_record(refusal)) is False
    assert suppression_filter.filter(_flow_run_record(_round_trip(refusal))) is False
