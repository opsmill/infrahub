from __future__ import annotations

from dataclasses import dataclass

import pytest
from git.exc import GitCommandError
from infrahub_sdk.exceptions import ServerNotReachableError, ServerNotResponsiveError

from infrahub.core.constants import RepositoryDeliveryFailureCause
from infrahub.exceptions import (
    DatabaseError,
    LockError,
    RepositoryConfigurationError,
    RepositoryConnectionError,
    RepositoryCredentialsError,
    RepositoryError,
    RepositoryNotFoundError,
    RepositoryPermissionError,
    RepositoryPushRejectedError,
    RepositoryTLSError,
)
from infrahub.git.base import InfrahubRepositoryBase
from infrahub.git.models import PushRejectionReason
from infrahub.git.writeback.classifier import classify_delivery_failure, scrub_credentials
from infrahub.git.writeback.models import DeliveryFailure, DeliveryStage

REPOSITORY = "net-repo"
LOCATION = "https://gitlab.example.com/net/repo.git"
CONNECTION_MESSAGE = "Unable to clone the repository net-repo, please check the address and the credential"
DATABASE_MESSAGE = "Unable to connect to the database"
TIME_LIMIT_MESSAGE = (
    "The Git command for repository net-repo did not complete within its time limit, "
    "please check that the remote is reachable."
)
NO_ORIGIN_MESSAGE = "The clone of repository net-repo on this worker has no origin."
KILLED_RESET_MESSAGE = "The command git reset did not complete within 120 seconds."
WORKER_PATH = "/var/lib/infrahub/repositories/net-repo"


def _caused_by(*, error: RepositoryError, cause: Exception) -> RepositoryError:
    error.__cause__ = cause
    return error


def _enriched_error(*, stderr: str, command: list[str], is_write_operation: bool) -> RepositoryError:
    try:
        InfrahubRepositoryBase._raise_enriched_error_static(
            error=GitCommandError(command=command, status=128, stderr=stderr),
            name=REPOSITORY,
            location=LOCATION,
            is_write_operation=is_write_operation,
        )
    except RepositoryError as exc:
        return exc


@dataclass
class ClassifyCase:
    name: str
    stage: DeliveryStage
    error: BaseException
    expected: DeliveryFailure


CLASSIFY_CASES: list[ClassifyCase] = [
    ClassifyCase(
        name="enqueue_failure_is_retried_and_keeps_the_cause",
        stage=DeliveryStage.ENQUEUE,
        error=DatabaseError(message=DATABASE_MESSAGE),
        expected=DeliveryFailure(cause=None, retryable=True, message=DATABASE_MESSAGE),
    ),
    ClassifyCase(
        name="enqueue_failure_without_a_message_names_its_type",
        stage=DeliveryStage.ENQUEUE,
        error=LockError(),
        expected=DeliveryFailure(
            cause=None, retryable=True, message="The enqueue step of the delivery failed with LockError."
        ),
    ),
    ClassifyCase(
        name="unreachable_remote_at_the_fetch_is_retried",
        stage=DeliveryStage.FETCH,
        error=RepositoryConnectionError(identifier=REPOSITORY),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE, retryable=True, message=CONNECTION_MESSAGE
        ),
    ),
    ClassifyCase(
        name="unreachable_remote_at_the_push_is_retried",
        stage=DeliveryStage.PUSH,
        error=RepositoryConnectionError(identifier=REPOSITORY),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE, retryable=True, message=CONNECTION_MESSAGE
        ),
    ),
    ClassifyCase(
        name="repository_not_found_at_the_fetch_is_not_retried",
        stage=DeliveryStage.FETCH,
        error=RepositoryNotFoundError(identifier=REPOSITORY),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.NOT_FOUND, retryable=False, message=CONNECTION_MESSAGE
        ),
    ),
    ClassifyCase(
        name="repository_not_found_at_the_push_is_not_retried",
        stage=DeliveryStage.PUSH,
        error=RepositoryNotFoundError(identifier=REPOSITORY),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.NOT_FOUND, retryable=False, message=CONNECTION_MESSAGE
        ),
    ),
    ClassifyCase(
        name="refused_certificate_at_the_fetch_is_not_retried",
        stage=DeliveryStage.FETCH,
        error=RepositoryTLSError(identifier=REPOSITORY),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.CERTIFICATE,
            retryable=False,
            message="SSL verification failed for net-repo, please validate the certificate chain.",
        ),
    ),
    ClassifyCase(
        name="refused_certificate_at_the_push_is_not_retried",
        stage=DeliveryStage.PUSH,
        error=RepositoryTLSError(identifier=REPOSITORY),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.CERTIFICATE,
            retryable=False,
            message="SSL verification failed for net-repo, please validate the certificate chain.",
        ),
    ),
    ClassifyCase(
        name="rejected_credentials_at_the_fetch_are_not_retried",
        stage=DeliveryStage.FETCH,
        error=RepositoryCredentialsError(identifier=REPOSITORY),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.CREDENTIALS,
            retryable=False,
            message="Authentication failed for net-repo, please validate the credentials.",
        ),
    ),
    ClassifyCase(
        name="credentials_lookup_failure_at_the_push_drops_the_secret_from_the_location",
        stage=DeliveryStage.PUSH,
        error=RepositoryCredentialsError(
            identifier=REPOSITORY,
            message=(
                "Unable to correctly lookup credentials for repository net-repo "
                "(https://admin:s3cret@gitlab.example.com/net/repo.git)."
            ),
        ),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.CREDENTIALS,
            retryable=False,
            message="Unable to correctly lookup credentials for repository net-repo (https://gitlab.example.com/net/repo.git).",
        ),
    ),
    ClassifyCase(
        name="clone_without_origin_at_the_fetch_is_unclassified",
        stage=DeliveryStage.FETCH,
        error=RepositoryError(identifier=REPOSITORY, message=NO_ORIGIN_MESSAGE),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.UNCLASSIFIED, retryable=False, message=NO_ORIGIN_MESSAGE
        ),
    ),
    ClassifyCase(
        name="denied_write_access_at_the_push_is_not_retried",
        stage=DeliveryStage.PUSH,
        error=RepositoryPermissionError(identifier=REPOSITORY),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.PERMISSION,
            retryable=False,
            message=(
                "Write access to repository net-repo was denied. The credentials can read but not push; "
                "grant the token write access to the repository."
            ),
        ),
    ),
    ClassifyCase(
        name="push_refused_by_a_hook_keeps_the_remote_lines_and_the_ref_summary",
        stage=DeliveryStage.PUSH,
        error=RepositoryPushRejectedError(
            identifier=REPOSITORY,
            reason=PushRejectionReason.POLICY,
            remote_message="remote: branch main is protected",
            message=(
                "Unable to push the branch main to the remote for repository net-repo: the remote refused the "
                "update (for example missing push permission or branch protection): "
                "[remote rejected] main (pre-receive hook declined)"
            ),
        ),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.PERMISSION,
            retryable=False,
            message=(
                "remote: branch main is protected\n"
                "Unable to push the branch main to the remote for repository net-repo: the remote refused the "
                "update (for example missing push permission or branch protection): "
                "[remote rejected] main (pre-receive hook declined)"
            ),
        ),
    ),
    ClassifyCase(
        name="push_refused_by_a_ruleset_is_a_permission_failure_whatever_its_wording",
        stage=DeliveryStage.PUSH,
        error=RepositoryPushRejectedError(
            identifier=REPOSITORY,
            reason=PushRejectionReason.POLICY,
            remote_message=(
                "remote: error: GH013: Repository rule violations found for refs/heads/main.\n"
                "remote: - Changes must be made through a pull request."
            ),
            message=(
                "Unable to push the branch main to the remote for repository net-repo: "
                "[remote rejected] main (push declined due to repository rule violations)"
            ),
        ),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.PERMISSION,
            retryable=False,
            message=(
                "remote: error: GH013: Repository rule violations found for refs/heads/main.\n"
                "remote: - Changes must be made through a pull request.\n"
                "Unable to push the branch main to the remote for repository net-repo: "
                "[remote rejected] main (push declined due to repository rule violations)"
            ),
        ),
    ),
    ClassifyCase(
        name="push_refused_as_non_fast_forward_is_retried",
        stage=DeliveryStage.PUSH,
        error=RepositoryPushRejectedError(
            identifier=REPOSITORY,
            reason=PushRejectionReason.NON_FAST_FORWARD,
            remote_message="",
            message=(
                "Unable to push the branch main to the remote for repository net-repo: the remote branch has "
                "commits that are missing locally (non-fast-forward): [rejected] main (fetch first)"
            ),
        ),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.REMOTE_ADVANCED,
            retryable=True,
            message=(
                "Unable to push the branch main to the remote for repository net-repo: the remote branch has "
                "commits that are missing locally (non-fast-forward): [rejected] main (fetch first)"
            ),
        ),
    ),
    ClassifyCase(
        name="push_refused_for_an_unknown_reason_is_unclassified",
        stage=DeliveryStage.PUSH,
        error=RepositoryPushRejectedError(
            identifier=REPOSITORY,
            reason=PushRejectionReason.UNKNOWN,
            remote_message="remote: see https://ci:t0ken@gitlab.example.com/help/push",
            message=(
                "Unable to push the branch main to the remote for repository net-repo: "
                "[remote failure] main (remote failed to report status)"
            ),
        ),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.UNCLASSIFIED,
            retryable=False,
            message=(
                "remote: see https://gitlab.example.com/help/push\n"
                "Unable to push the branch main to the remote for repository net-repo: "
                "[remote failure] main (remote failed to report status)"
            ),
        ),
    ),
    ClassifyCase(
        name="record_failure_is_retried",
        stage=DeliveryStage.RECORD,
        error=DatabaseError(message=DATABASE_MESSAGE),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.RECORD_FAILED, retryable=True, message=DATABASE_MESSAGE
        ),
    ),
    ClassifyCase(
        name="record_failure_is_retried_whatever_the_error",
        stage=DeliveryStage.RECORD,
        error=RepositoryNotFoundError(identifier=REPOSITORY),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.RECORD_FAILED, retryable=True, message=CONNECTION_MESSAGE
        ),
    ),
    ClassifyCase(
        name="database_outage_at_the_import_is_retried",
        stage=DeliveryStage.IMPORT,
        error=DatabaseError(message=DATABASE_MESSAGE),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.IMPORT_INTERRUPTED, retryable=True, message=DATABASE_MESSAGE
        ),
    ),
    ClassifyCase(
        name="unreachable_remote_at_the_import_is_retried",
        stage=DeliveryStage.IMPORT,
        error=RepositoryConnectionError(identifier=REPOSITORY),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.IMPORT_INTERRUPTED, retryable=True, message=CONNECTION_MESSAGE
        ),
    ),
    ClassifyCase(
        name="unreachable_api_server_at_the_import_is_retried",
        stage=DeliveryStage.IMPORT,
        error=ServerNotReachableError(address="http://infrahub-server:8000"),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.IMPORT_INTERRUPTED,
            retryable=True,
            message="The import step of the delivery failed with ServerNotReachableError.",
        ),
    ),
    ClassifyCase(
        name="unresponsive_api_server_at_the_import_is_retried",
        stage=DeliveryStage.IMPORT,
        error=ServerNotResponsiveError(url="http://infrahub-server:8000/graphql/main", timeout=60),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.IMPORT_INTERRUPTED,
            retryable=True,
            message="The import step of the delivery failed with ServerNotResponsiveError.",
        ),
    ),
    ClassifyCase(
        name="invalid_content_at_the_import_is_not_retried",
        stage=DeliveryStage.IMPORT,
        error=RepositoryConfigurationError(
            identifier=REPOSITORY, message="The repository configuration file .infrahub.yml is not valid."
        ),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.IMPORT_FAILED,
            retryable=False,
            message="The repository configuration file .infrahub.yml is not valid.",
        ),
    ),
    ClassifyCase(
        name="unexpected_error_at_the_import_is_not_retried",
        stage=DeliveryStage.IMPORT,
        error=KeyError("artifact_definitions"),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.IMPORT_FAILED,
            retryable=False,
            message="The import step of the delivery failed with KeyError.",
        ),
    ),
    ClassifyCase(
        name="killed_local_command_at_the_replay_names_the_command",
        stage=DeliveryStage.REPLAY,
        error=_caused_by(
            error=RepositoryError(identifier=REPOSITORY, message=KILLED_RESET_MESSAGE),
            cause=GitCommandError(
                command=["git", "reset", "--hard", "0123456789abcdef"],
                status=-9,
                stderr=f'Timeout: the command "git -C {WORKER_PATH} reset --hard 0123456789abcdef" did not complete',
            ),
        ),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.UNCLASSIFIED, retryable=False, message=KILLED_RESET_MESSAGE
        ),
    ),
    ClassifyCase(
        name="release_failure_is_retried_and_keeps_the_cause",
        stage=DeliveryStage.RELEASE,
        error=TimeoutError(),
        expected=DeliveryFailure(
            cause=None, retryable=True, message="The release step of the delivery failed with TimeoutError."
        ),
    ),
    ClassifyCase(
        name="release_failure_is_retried_whatever_the_error",
        stage=DeliveryStage.RELEASE,
        error=RepositoryNotFoundError(identifier=REPOSITORY),
        expected=DeliveryFailure(cause=None, retryable=True, message=CONNECTION_MESSAGE),
    ),
    ClassifyCase(
        name="other_repository_error_at_the_push_is_unclassified",
        stage=DeliveryStage.PUSH,
        error=RepositoryError(
            identifier=REPOSITORY,
            message="Commit not found in the local clone of repository net-repo; it may have been force-pushed or pruned upstream.",
        ),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.UNCLASSIFIED,
            retryable=False,
            message="Commit not found in the local clone of repository net-repo; it may have been force-pushed or pruned upstream.",
        ),
    ),
    ClassifyCase(
        name="unexpected_error_at_the_fetch_is_unclassified",
        stage=DeliveryStage.FETCH,
        error=ValueError(f"no such directory {WORKER_PATH}"),
        expected=DeliveryFailure(
            cause=RepositoryDeliveryFailureCause.UNCLASSIFIED,
            retryable=False,
            message="The fetch step of the delivery failed with ValueError.",
        ),
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in CLASSIFY_CASES])
def test_classify_delivery_failure(case: ClassifyCase) -> None:
    assert classify_delivery_failure(error=case.error, stage=case.stage) == case.expected


@dataclass
class KilledCommandCase:
    name: str
    stage: DeliveryStage
    command: list[str]
    is_write_operation: bool


KILLED_COMMAND_CASES: list[KilledCommandCase] = [
    KilledCommandCase(
        name="killed_fetch", stage=DeliveryStage.FETCH, command=["git", "fetch", "origin"], is_write_operation=False
    ),
    KilledCommandCase(
        name="killed_push",
        stage=DeliveryStage.PUSH,
        command=["git", "push", "origin", "HEAD:refs/heads/main"],
        is_write_operation=True,
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in KILLED_COMMAND_CASES])
def test_killed_remote_command_is_retried_as_an_unreachable_remote(case: KilledCommandCase) -> None:
    error = _enriched_error(
        stderr="error: process killed because it timed out. kill_after_timeout=120 seconds",
        command=case.command,
        is_write_operation=case.is_write_operation,
    )

    assert classify_delivery_failure(error=error, stage=case.stage) == DeliveryFailure(
        cause=RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE, retryable=True, message=TIME_LIMIT_MESSAGE
    )


def test_unmatched_git_failure_gives_its_type_and_not_the_git_output() -> None:
    stderr = f"error: unable to create temporary file {WORKER_PATH}/objects/pack/tmp_pack: No space left on device"
    error = _enriched_error(stderr=stderr, command=["git", "push", "origin"], is_write_operation=True)
    assert stderr in error.message

    failure = classify_delivery_failure(error=error, stage=DeliveryStage.PUSH)

    assert failure == DeliveryFailure(
        cause=RepositoryDeliveryFailureCause.UNCLASSIFIED,
        retryable=False,
        message="The push step of the delivery failed with RepositoryError.",
    )


def test_git_error_gives_its_type_and_not_the_git_output() -> None:
    error = GitCommandError(
        command=["git", "fetch", "origin"],
        status=128,
        stderr=f"fatal: not a git repository: {WORKER_PATH}/.git",
    )

    failure = classify_delivery_failure(error=error, stage=DeliveryStage.FETCH)

    assert failure == DeliveryFailure(
        cause=RepositoryDeliveryFailureCause.UNCLASSIFIED,
        retryable=False,
        message="The fetch step of the delivery failed with GitCommandError.",
    )


def test_merge_failure_built_from_the_git_output_gives_its_type() -> None:
    cause = GitCommandError(
        command=["git", "merge", "0123456789abcdef", "--no-ff"],
        status=1,
        stderr=f"error: Your local changes to the following files would be overwritten by merge:\n\t{WORKER_PATH}/a.yml",
    )
    error = _caused_by(error=RepositoryError(identifier=REPOSITORY, message=cause.stderr), cause=cause)

    failure = classify_delivery_failure(error=error, stage=DeliveryStage.REPLAY)

    assert failure == DeliveryFailure(
        cause=RepositoryDeliveryFailureCause.UNCLASSIFIED,
        retryable=False,
        message="The replay step of the delivery failed with RepositoryError.",
    )


def test_typed_error_from_the_git_output_gives_its_typed_message() -> None:
    error = _enriched_error(
        stderr=(
            "fatal: unable to access 'https://admin:s3cret@gitlab.example.com/net/repo.git/': "
            "Could not resolve host: gitlab.example.com"
        ),
        command=["git", "fetch", "origin"],
        is_write_operation=False,
    )

    failure = classify_delivery_failure(error=error, stage=DeliveryStage.FETCH)

    assert failure == DeliveryFailure(
        cause=RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE, retryable=True, message=CONNECTION_MESSAGE
    )


@dataclass
class ScrubCase:
    name: str
    text: str
    expected: str


SCRUB_CASES: list[ScrubCase] = [
    ScrubCase(
        name="user_and_token",
        text="fatal: unable to access 'https://admin:s3cret@gitlab.example.com/net/repo.git/'",
        expected="fatal: unable to access 'https://gitlab.example.com/net/repo.git/'",
    ),
    ScrubCase(
        name="user_alone",
        text="Cloning from https://deploy@gitlab.example.com/net/repo.git failed",
        expected="Cloning from https://gitlab.example.com/net/repo.git failed",
    ),
    ScrubCase(
        name="password_holding_an_at_sign",
        text="https://admin:p@ss@gitlab.example.com/net/repo.git",
        expected="https://gitlab.example.com/net/repo.git",
    ),
    ScrubCase(
        name="several_urls_in_one_text",
        text=(
            "remote: mirrored from https://ci:t0ken@one.example.com/a.git to http://bot@two.example.com:8080/b.git\n"
            "remote: and ssh://git@three.example.com/c.git"
        ),
        expected=(
            "remote: mirrored from https://one.example.com/a.git to http://two.example.com:8080/b.git\n"
            "remote: and ssh://three.example.com/c.git"
        ),
    ),
    ScrubCase(
        name="url_right_after_an_underscore",
        text="loc=_https://u:tok@h",
        expected="loc=_https://h",
    ),
    ScrubCase(
        name="url_right_after_a_digit",
        text="1https://u:tok@h",
        expected="1https://h",
    ),
    ScrubCase(
        name="text_with_no_credentials_stays_as_it_is",
        text="Ask admin@example.com about https://gitlab.example.com:8443/team@infra/repo.git?ref=a@b",
        expected="Ask admin@example.com about https://gitlab.example.com:8443/team@infra/repo.git?ref=a@b",
    ),
]


@pytest.mark.parametrize("case", [pytest.param(case, id=case.name) for case in SCRUB_CASES])
def test_scrub_credentials(case: ScrubCase) -> None:
    assert scrub_credentials(text=case.text) == case.expected
