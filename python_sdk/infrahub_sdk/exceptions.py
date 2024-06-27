from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


class Error(Exception):
    def __init__(self, message: str | None = None):
        self.message = message
        super().__init__(self.message)


class JsonDecodeError(Error):
    def __init__(self, message: str | None = None, content: str | None = None, url: str | None = None):
        self.message = message
        self.content = content
        self.url = url
        if not self.message and self.url:
            self.message = f"Unable to decode response as JSON data from {self.url}"
        super().__init__(self.message)


class ServerNotReachableError(Error):
    def __init__(self, address: str, message: str | None = None):
        self.address = address
        self.message = message or f"Unable to connect to '{address}'."
        super().__init__(self.message)


class ServerNotResponsiveError(Error):
    def __init__(self, url: str, timeout: int | None = None, message: str | None = None):
        self.url = url
        self.timeout = timeout
        self.message = message or f"Unable to read from '{url}'."
        if timeout:
            self.message += f" (timeout: {timeout} sec)"
        super().__init__(self.message)


class GraphQLError(Error):
    def __init__(self, errors: list[dict[str, Any]], query: str | None = None, variables: dict | None = None):
        self.query = query
        self.variables = variables
        self.errors = errors
        self.message = f"An error occurred while executing the GraphQL Query {self.query}, {self.errors}"
        super().__init__(self.message)


class BranchNotFoundError(Error):
    def __init__(self, identifier: str, message: str | None = None):
        self.identifier = identifier
        self.message = message or f"Unable to find the branch '{identifier}' in the Database."
        super().__init__(self.message)


class SchemaNotFoundError(Error):
    def __init__(self, identifier: str, message: str | None = None):
        self.identifier = identifier
        self.message = message or f"Unable to find the schema '{identifier}'."
        super().__init__(self.message)


class ModuleImportError(Error):
    def __init__(self, message: str | None = None):
        self.message = message or "Unable to import the module"
        super().__init__(self.message)


class NodeNotFoundError(Error):
    def __init__(
        self,
        node_type: str,
        identifier: Mapping[str, list[str]],
        message: str = "Unable to find the node in the database.",
        branch_name: str | None = None,
    ):
        self.node_type = node_type
        self.identifier = identifier
        self.branch_name = branch_name

        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"""
        {self.message}
        {self.branch_name} | {self.node_type} | {self.identifier}
        """


class FilterNotFoundError(Error):
    def __init__(self, identifier: str, kind: str, message: str | None = None, filters: list[str] | None = None):
        self.identifier = identifier
        self.kind = kind
        self.filters = filters or []
        self.message = message or f"{identifier!r} is not a valid filter for {self.kind!r} ({', '.join(self.filters)})."
        super().__init__(self.message)


class InfrahubCheckNotFoundError(Error):
    def __init__(self, name: str, message: str | None = None):
        self.message = message or f"The requested InfrahubCheck '{name}' was not found."
        super().__init__(self.message)


class InfrahubTransformNotFoundError(Error):
    def __init__(self, name: str, message: str | None = None):
        self.message = message or f"The requested InfrahubTransform '{name}' was not found."
        super().__init__(self.message)


class ValidationError(Error):
    def __init__(self, identifier: str, message: str):
        self.identifier = identifier
        self.message = message
        super().__init__(self.message)


class AuthenticationError(Error):
    def __init__(self, message: str | None = None):
        self.message = message or "Authentication Error, unable to execute the query."
        super().__init__(self.message)


class FeatureNotSupportedError(Error):
    """Raised when trying to use a method on a node that doesn't support it."""


class UninitializedError(Error):
    """Raised when an object requires an initialization step before use"""


class InvalidResponseError(Error):
    """Raised when an object requires an initialization step before use"""
