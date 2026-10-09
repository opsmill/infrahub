from __future__ import annotations

from infrahub_sdk.exceptions import ServerNotReachableError, ServerNotResponsiveError

from infrahub.core.constants import RepositoryDeliveryFailureCause
from infrahub.exceptions import (
    DatabaseError,
    Error,
    RepositoryConnectionError,
    RepositoryCredentialsError,
    RepositoryNotFoundError,
    RepositoryPermissionError,
    RepositoryPushRejectedError,
    RepositoryTLSError,
)
from infrahub.git.models import PushRejectionReason
from infrahub.git.writeback.credentials import scrub_credentials
from infrahub.git.writeback.models import DeliveryFailure, DeliveryStage

RETRIED_CAUSES = frozenset(
    {
        RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE,
        RepositoryDeliveryFailureCause.REMOTE_ADVANCED,
        RepositoryDeliveryFailureCause.RECORD_FAILED,
        RepositoryDeliveryFailureCause.IMPORT_INTERRUPTED,
    }
)

PUSH_REJECTION_CAUSES: dict[PushRejectionReason, RepositoryDeliveryFailureCause] = {
    PushRejectionReason.POLICY: RepositoryDeliveryFailureCause.PERMISSION,
    PushRejectionReason.NON_FAST_FORWARD: RepositoryDeliveryFailureCause.REMOTE_ADVANCED,
    PushRejectionReason.REF_UPDATE_FAILED: RepositoryDeliveryFailureCause.REMOTE_ADVANCED,
    PushRejectionReason.UNKNOWN: RepositoryDeliveryFailureCause.UNCLASSIFIED,
}

IMPORT_INTERRUPTIONS: tuple[type[Exception], ...] = (
    DatabaseError,
    RepositoryConnectionError,
    ServerNotReachableError,
    ServerNotResponsiveError,
)


def classify_delivery_failure(*, error: BaseException, stage: DeliveryStage) -> DeliveryFailure:
    """Return why a step of a delivery failed, whether a retry can succeed, and a message that is safe to store.

    A failed enqueue or release gives no cause, as neither is a failure of the delivery to the remote. The
    message is the remote's own words for a refused push, or the message of another Infrahub error when it does
    not repeat Git output. Any other error gives a sentence that names the step and the error type.
    """
    message = scrub_credentials(text=_describe(error=error, stage=stage))
    match stage:
        case DeliveryStage.ENQUEUE | DeliveryStage.RELEASE:
            return DeliveryFailure(cause=None, retryable=True, message=message)
        case DeliveryStage.FETCH:
            cause = _remote_cause(error=error)
        case DeliveryStage.PUSH:
            cause = _push_cause(error=error)
        case DeliveryStage.RECORD:
            cause = RepositoryDeliveryFailureCause.RECORD_FAILED
        case DeliveryStage.IMPORT:
            cause = _import_cause(error=error)
        case DeliveryStage.REPLAY:
            cause = RepositoryDeliveryFailureCause.UNCLASSIFIED
    return DeliveryFailure(cause=cause, retryable=cause in RETRIED_CAUSES, message=message)


def _remote_cause(*, error: BaseException) -> RepositoryDeliveryFailureCause:
    # Both subtypes are connection errors, so they come first.
    if isinstance(error, RepositoryNotFoundError):
        return RepositoryDeliveryFailureCause.NOT_FOUND
    if isinstance(error, RepositoryTLSError):
        return RepositoryDeliveryFailureCause.CERTIFICATE
    if isinstance(error, RepositoryConnectionError):
        return RepositoryDeliveryFailureCause.REMOTE_UNREACHABLE
    if isinstance(error, RepositoryCredentialsError):
        return RepositoryDeliveryFailureCause.CREDENTIALS
    return RepositoryDeliveryFailureCause.UNCLASSIFIED


def _import_cause(*, error: BaseException) -> RepositoryDeliveryFailureCause:
    # A missing repository or a refused certificate is a connection error that no retry fixes, at any stage.
    if isinstance(error, (RepositoryNotFoundError, RepositoryTLSError)):
        return _remote_cause(error=error)
    if isinstance(error, IMPORT_INTERRUPTIONS):
        return RepositoryDeliveryFailureCause.IMPORT_INTERRUPTED
    return RepositoryDeliveryFailureCause.IMPORT_FAILED


def _push_cause(*, error: BaseException) -> RepositoryDeliveryFailureCause:
    if isinstance(error, RepositoryPushRejectedError):
        return PUSH_REJECTION_CAUSES[error.reason]
    if isinstance(error, RepositoryPermissionError):
        return RepositoryDeliveryFailureCause.PERMISSION
    return _remote_cause(error=error)


def _describe(*, error: BaseException, stage: DeliveryStage) -> str:
    if isinstance(error, RepositoryPushRejectedError):
        return "\n".join(part for part in (error.remote_message, error.message) if part)
    if isinstance(error, Error) and error.message and not _repeats_its_cause(error=error):
        return error.message
    return f"The {stage} step of the delivery failed with {type(error).__name__}."


def _repeats_its_cause(*, error: Error) -> bool:
    # An error built from the output of a Git command repeats it, and that output can name paths on the worker.
    return error.__cause__ is not None and error.message in str(error.__cause__)
