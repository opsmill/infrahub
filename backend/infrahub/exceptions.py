from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub.core.diff.model.diff import SchemaConflict
    from infrahub.core.validators.model import SchemaViolation


def _rebuild_error(cls: type[Error], args: tuple[Any, ...], state: Any) -> Error:
    obj = cls.__new__(cls)
    obj.args = args
    # Mirror object.__setstate__: state is a dict of instance attributes, or a
    # (dict_state, slots_state) tuple for subclasses that define __slots__, or None.
    if state is not None:
        dict_state, slots_state = state if isinstance(state, tuple) else (state, None)
        if dict_state:
            obj.__dict__.update(dict_state)
        if slots_state:
            for key, value in slots_state.items():
                setattr(obj, key, value)
    return obj


class Error(Exception):
    HTTP_CODE: int = 500
    DESCRIPTION: str = "Unknown Error"
    message: str = ""
    errors: list | None = None

    def __reduce__(self) -> tuple[Any, ...]:
        # BaseException.__reduce__ rebuilds via cls(*self.args), dropping any additional required
        # constructor arguments, so subclasses with extra parameters fail to unpickle. Rebuild via
        # __new__ + instance state instead so every subclass round-trips regardless of its
        # __init__ signature. __getstate__ captures both __dict__ and __slots__ state so
        # slotted subclasses round-trip too.
        return (_rebuild_error, (self.__class__, self.args, self.__getstate__()))

    def api_response(self) -> dict[str, Any]:
        """Return error response."""
        if isinstance(self.errors, list):
            return {"data": None, "errors": self.errors}
        return {
            "data": None,
            "errors": [{"message": str(self.message) or self.DESCRIPTION, "extensions": {"code": self.HTTP_CODE}}],
        }


class PropagatedFromWorkerError(Error):
    """Used to re-raise server side an error that happened worker side.

    Note we might want to improve this so we raise the exact same error that happened worker side.
    """

    def __init__(self, http_code: int, message: str) -> None:
        self.HTTP_CODE = http_code
        self.message = message


class RPCError(Error):
    HTTP_CODE: int = 502

    def __init__(self, message: str) -> None:
        self.message = message


class InitializationError(Error):
    DESCRIPTION: str = "The application hasn't been initialized properly"


class DatabaseError(Error):
    HTTP_CODE: int = 503
    DESCRIPTION = "Database unavailable"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class ServiceUnavailableError(Error):
    HTTP_CODE: int = 503
    DESCRIPTION = "Service unavailable"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class LockError(Error):
    pass


class RedisUrlError(Error):
    """Raised when a Redis connection URL cannot be parsed into a valid connection."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class GraphQLQueryError(Error):
    HTTP_CODE = 502

    def __init__(self, errors: list) -> None:
        self.errors = errors


class RepositoryError(Error):
    def __init__(self, identifier: str, message: str | None = None) -> None:
        self.identifier = identifier
        self.message = message or f"An error occurred with GitRepository '{identifier}'."
        super().__init__(self.message)


class RepositoryConnectionError(RepositoryError):
    def __init__(self, identifier: str, message: str | None = None) -> None:
        super().__init__(
            identifier=identifier,
            message=message
            or f"Unable to clone the repository {identifier}, please check the address and the credential",
        )


class RepositoryCredentialsError(RepositoryError):
    def __init__(self, identifier: str, message: str | None = None) -> None:
        super().__init__(
            identifier=identifier,
            message=message or f"Authentication failed for {identifier}, please validate the credentials.",
        )


class RepositoryInvalidBranchError(RepositoryError):
    def __init__(self, identifier: str, branch_name: str, location: str, message: str | None = None) -> None:
        super().__init__(
            identifier=identifier,
            message=message
            or f"The branch {branch_name} isn't a valid branch for the repository {identifier} at {location}.",
        )


class RepositoryInvalidFileSystemError(RepositoryError):
    def __init__(
        self,
        identifier: str,
        directory: Path,
        message: str | None = None,
    ) -> None:
        super().__init__(
            identifier=identifier,
            message=message or f"Invalid file system for {identifier}, Local directory {directory} missing.",
        )
        self.directory = directory


class RepositoryConfigurationError(RepositoryError):
    """Raised when repository configuration file is missing or invalid."""

    def __init__(self, identifier: str, message: str | None = None) -> None:
        super().__init__(
            identifier=identifier,
            message=message or "Repository configuration file error.",
        )


class CommitNotFoundError(Error):
    HTTP_CODE: int = 400

    def __init__(self, identifier: str, commit: str, message: str | None = None) -> None:
        self.identifier = identifier
        self.commit = commit
        self.message = message or f"Commit {commit} not found with GitRepository '{identifier}'."
        super().__init__(self.message)


class DataTypeNotFoundError(Error):
    HTTP_CODE: int = 400

    def __init__(self, name: str, message: str | None = None) -> None:
        self.name = name
        self.message = message or f"Unable to find the DataType '{name}'."
        super().__init__(self.message)


class RepositoryFileNotFoundError(Error):
    HTTP_CODE: int = 404

    def __init__(self, repository_name: str, location: str, commit: str, message: str | None = None) -> None:
        self.repository_name = repository_name
        self.location = location
        self.commit = commit
        self.message = message or f"Unable to find the file at '{repository_name}::{commit}::{location}'."
        super().__init__(self.message)


class FileOutOfRepositoryError(Error):
    HTTP_CODE: int = 403

    def __init__(self, repository_name: str, location: str, commit: str, message: str | None = None) -> None:
        self.repository_name = repository_name
        self.location = location
        self.commit = commit
        self.message = message or f"File not in repository '{repository_name}::{commit}::{location}'."
        super().__init__(self.message)


class TransformError(Error):
    def __init__(self, repository_name: str, location: str, commit: str, message: str | None = None) -> None:
        self.repository_name = repository_name
        self.location = location
        self.commit = commit
        self.message = (
            message or f"An error occurred with the transform function at '{repository_name}::{commit}::{location}'."
        )
        super().__init__(self.message)


class CheckError(Error):
    def __init__(
        self, repository_name: str, location: str, class_name: str, commit: str, message: str | None = None
    ) -> None:
        self.repository_name = repository_name
        self.location = location
        self.commit = commit
        self.class_name = class_name
        self.message = (
            message
            or f"An error occurred with the check function at '{repository_name}::{commit}::{location}::{class_name}'."
        )
        super().__init__(self.message)


class TransformNotFoundError(TransformError):
    def __init__(self, repository_name: str, location: str, commit: str, message: str | None = None) -> None:
        self.message = (
            message or f"Unable to locate the transform function at '{repository_name}::{commit}::{location}'."
        )
        super().__init__(repository_name, location, commit, self.message)


class BranchNotFoundError(Error):
    HTTP_CODE: int = 400

    def __init__(self, identifier: str, message: str | None = None) -> None:
        self.identifier = identifier
        self.message = message or f"Branch: {identifier} not found."
        super().__init__(self.message)


class NodeNotFoundError(Error):
    HTTP_CODE: int = 404

    def __init__(
        self, node_type: str, identifier: str, branch_name: str | None = None, message: str | None = None
    ) -> None:
        self.node_type = node_type
        self.identifier = identifier
        self.branch_name = branch_name
        self.message = message or f"Unable to find the node {identifier} / {node_type} in the database."
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"""
        {self.message}
        {self.branch_name} | {self.node_type} | {self.identifier}
        """


class ResourceNotFoundError(Error):
    HTTP_CODE: int = 404

    def __init__(self, message: str | None = None) -> None:
        self.message = message or "The requested resource was not found"
        super().__init__(self.message)


class ResourceMultipleFoundError(Error):
    HTTP_CODE: int = 500

    def __init__(self, message: str | None = None) -> None:
        self.message = message or "Multiple matching resources were found"
        super().__init__(self.message)


class AuthorizationError(Error):
    HTTP_CODE: int = 401
    message: str = "Access to the requested resource was denied"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class ForwardableError(Error):
    """Base class for exceptions that can be forwarded to log forwarding destinations."""

    log_forwarded: bool = False


class PermissionDeniedError(ForwardableError):
    HTTP_CODE: int = 403
    message: str = "The requested operation was not authorized"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class ProcessingError(Error):
    HTTP_CODE: int = 400
    message: str = "Unable to process the request"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class PoolExhaustedError(Error):
    HTTP_CODE: int = 409
    message: str = "No more resources available in the pool"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class SchemaNotFoundError(Error):
    HTTP_CODE: int = 422

    def __init__(self, branch_name: str, identifier: str, message: str | None = None) -> None:
        self.branch_name = branch_name
        self.identifier = identifier
        self.message = message or f"Unable to find the schema {identifier} in the database."
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"""
        {self.message}
        {self.branch_name} | {self.identifier}
        """


class QueryError(Error):
    def __init__(self, query: str, params: dict, message: str = "Unable to execute the CYPHER query.") -> None:
        self.query = query
        self.params = params

        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"""
        {self.message}
        {self.query}
        {self.params}
        """


class QueryTimeoutError(Error):
    HTTP_CODE: int = 504

    def __init__(self, message: str = "The query exceeded its execution time budget.") -> None:
        self.message = message
        super().__init__(self.message)


class QueryValidationError(Error):
    HTTP_CODE = 400

    def __init__(self, message: str) -> None:
        self.message = message


class GatewayError(Error):
    HTTP_CODE = 502

    def __init__(self, message: str) -> None:
        self.message = message


class MigrationError(Error):
    HTTP_CODE = 502

    def __init__(self, message: str) -> None:
        self.message = message


class ValidationError(Error):
    HTTP_CODE = 422

    def __init__(self, input_value: str | dict | list) -> None:
        self.input_value = input_value
        self.message = ""

        if isinstance(input_value, str):
            self.message = input_value
        elif isinstance(input_value, dict):
            self.message = ", ".join([f"{message} at {location}" for location, message in input_value.items()])
        elif isinstance(input_value, list):
            if all(isinstance(item, ValidationError) for item in input_value):
                self.message = ", ".join([validation_error.message for validation_error in input_value])
            if all(isinstance(item, dict) for item in input_value):
                messages = []
                for item in input_value:
                    messages.append(", ".join([f"{message} at {location}" for location, message in item.items()]))
                self.message = ", ".join(messages)

        if not self.message:
            raise ValueError("Could not build validation error message")

        super().__init__(self.message)


class DiffError(Error):
    HTTP_CODE = 400

    def __init__(self, message: str) -> None:
        self.message = message


class UniquenessViolationError(ValidationError):
    """Raised when a node's uniqueness constraint is violated."""


class HFIDViolatedError(UniquenessViolationError):
    matching_nodes_ids: set[str]

    def __init__(self, input_value: str | dict | list, matching_nodes_ids: set[str]) -> None:
        self.matching_nodes_ids = matching_nodes_ids
        super().__init__(input_value)


class DiffRangeValidationError(DiffError): ...


class DiffFromRequiredOnDefaultBranchError(DiffError): ...


class HTTPServerError(Error):
    """Errors raised when communicating with external HTTP servers."""

    HTTP_CODE = 502

    def __init__(self, message: str) -> None:
        self.message = message


class HTTPServerTimeoutError(HTTPServerError):
    HTTP_CODE = 504


class HTTPServerSSLError(HTTPServerError):
    HTTP_CODE = 503


class MergeFailedError(Error):
    HTTP_CODE: int = 500

    def __init__(self, branch_name: str) -> None:
        self.message = f"Failed to merge branch '{branch_name}'"
        super().__init__(self.message)


class MergeConstraintsViolatedError(ValidationError):
    """Raised when merging a branch would violate a schema/data constraint on the destination."""

    def __init__(self, violations: list[SchemaViolation], schema_conflicts: list[SchemaConflict]) -> None:
        self.violations = violations
        self.schema_conflicts = schema_conflicts
        super().__init__(",\n".join(violation.message for violation in violations) or "Merge constraints violated")


class MergeConflictsUnresolvedError(ValidationError):
    """Raised when a branch cannot be merged because conflicts with the destination are unresolved."""

    def __init__(self, conflict_paths: list[str], branch_name: str) -> None:
        self.conflict_paths = conflict_paths
        self.branch_name = branch_name
        super().__init__(
            f"Unable to merge the branch '{branch_name}', conflict resolution missing: {', '.join(conflict_paths)}"
        )


class BranchStatusError(Error):
    HTTP_CODE: int = 400

    def __init__(self, identifier: str, message: str) -> None:
        self.identifier = identifier
        self.message = message
        super().__init__(self.message)


class BranchAlreadyMergedError(BranchStatusError): ...


class BranchNeedsRebaseError(BranchStatusError): ...


class MergeInProgressError(BranchStatusError):
    """Write rejected because a merge is in progress on `merging_branch`."""

    HTTP_CODE: int = 423

    def __init__(self, identifier: str, message: str, merging_branch: str) -> None:
        self.merging_branch = merging_branch
        super().__init__(identifier=identifier, message=message)


class MergeRecoveryRequiredError(BranchStatusError):
    """Write rejected because a failed merge needs operator recovery.

    `merging_branch` is the source branch that was being merged (the one whose merge died);
    `identifier` is the branch the rejected write targeted (the source branch itself or the
    default branch).

    Deliberately a sibling of MergeInProgressError, not a subclass: an in-progress merge is
    transient and retryable, while this indicates recovery is required.
    """

    HTTP_CODE: int = 423

    def __init__(self, identifier: str, message: str, merging_branch: str) -> None:
        self.merging_branch = merging_branch
        super().__init__(identifier=identifier, message=message)


class EnterpriseRequiredError(Error):
    """Raised when a community deployment invokes an Enterprise-gated feature.

    The `feature` attribute carries the stable, snake_case feature identifier (e.g. `"ldap_auth"`).
    """

    HTTP_CODE: int = 403
    DESCRIPTION: str = "This feature requires the Infrahub Enterprise edition."

    def __init__(self, feature: str, message: str | None = None) -> None:
        self.feature = feature
        self.message = message or self.DESCRIPTION
        super().__init__(self.message)


class LDAPAuthenticationError(Error):
    """Generic LDAP authentication failure.

    Raised for wrong password, unknown user, disabled account, and any other
    bind/search failure that should appear to the end user as a generic
    credential failure. Never discloses the underlying cause.
    """

    HTTP_CODE: int = 401
    message: str = "Authentication failed."


class LDAPLookupError(LDAPAuthenticationError):
    """LDAP user search returned multiple entries or a referral."""


class LDAPDirectoryUnavailableError(Error):
    """All configured LDAP servers timed out or refused the connection."""

    HTTP_CODE: int = 502
    message: str = "The LDAP directory is currently unavailable. Try again later."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class LDAPCollisionError(Error):
    """LDAP login attempted for a username that exists as a local-only account."""

    HTTP_CODE: int = 409
    DESCRIPTION: str = (
        "An account already exists for this username and is not attributed to LDAP. Contact your administrator."
    )

    def __init__(self, account_name: str, message: str | None = None) -> None:
        self.account_name = account_name
        self.message = message or self.DESCRIPTION
        super().__init__(self.message)
