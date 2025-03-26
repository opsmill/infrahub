from pathlib import Path
from typing import Any


class Error(Exception):
    HTTP_CODE: int = 500
    DESCRIPTION: str = "Unknown Error"
    message: str = ""
    errors: list | None = None

    def api_response(self) -> dict[str, Any]:
        """Return error response."""
        if isinstance(self.errors, list):
            return {"data": None, "errors": self.errors}
        return {
            "data": None,
            "errors": [{"message": str(self.message) or self.DESCRIPTION, "extensions": {"code": self.HTTP_CODE}}],
        }


class PropagatedFromWorkerError(Error):
    """
    Used to re-raise server side an error that happened worker side.
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


class AuthorizationError(Error):
    HTTP_CODE: int = 401
    message: str = "Access to the requested resource was denied"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class PermissionDeniedError(Error):
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


class HFIDViolatedError(ValidationError):
    matching_nodes_ids: set[str]

    def __init__(self, input_value: str | dict | list, matching_nodes_ids: set[str]) -> None:
        self.matching_nodes_ids = matching_nodes_ids
        super().__init__(input_value)


class DiffRangeValidationError(DiffError): ...


class DiffFromRequiredOnDefaultBranchError(DiffError): ...


class HTTPServerError(Error):
    """Errors raised when communicating with external HTTP servers"""

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
