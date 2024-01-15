from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional


class Error(Exception):
    def __init__(self, message: Optional[str] = None):
        self.message = message
        super().__init__(self.message)


class ServerNotReacheableError(Error):
    def __init__(self, address: str, message: Optional[str] = None):
        self.address = address
        self.message = message or f"Unable to connect to '{address}'."
        super().__init__(self.message)


class ServerNotResponsiveError(Error):
    def __init__(self, url: str, timeout: Optional[int] = None, message: Optional[str] = None):
        self.url = url
        self.timeout = timeout
        self.message = message or f"Unable to read from '{url}'."
        if timeout:
            self.message += f" (timeout: {timeout} sec)"
        super().__init__(self.message)


class GraphQLError(Error):
    def __init__(
        self,
        errors: List[Dict[str, Any]],
        query: Optional[str] = None,
        variables: Optional[dict] = None,
    ):
        self.query = query
        self.variables = variables
        self.errors = errors
        self.message = f"An error occured while executing the GraphQL Query {self.query}, {self.errors}"
        super().__init__(self.message)


class BranchNotFound(Error):
    def __init__(self, identifier: str, message: Optional[str] = None):
        self.identifier = identifier
        self.message = message or f"Unable to find the branch '{identifier}' in the Database."
        super().__init__(self.message)


class SchemaNotFound(Error):
    def __init__(self, identifier: str, message: Optional[str] = None):
        self.identifier = identifier
        self.message = message or f"Unable to find the schema '{identifier}'."
        super().__init__(self.message)


class NodeNotFound(Error):
    def __init__(
        self,
        branch_name: str,
        node_type: str,
        identifier: Mapping[str, List[str]],
        message: str = "Unable to find the node in the database.",
    ):
        self.branch_name = branch_name
        self.node_type = node_type
        self.identifier = identifier

        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"""
        {self.message}
        {self.branch_name} | {self.node_type} | {self.identifier}
        """


class FilterNotFound(Error):
    def __init__(
        self,
        identifier: str,
        kind: str,
        message: Optional[str] = None,
        filters: Optional[List[str]] = None,
    ):
        self.identifier = identifier
        self.kind = kind
        self.filters = filters or []
        self.message = message or f"{identifier!r} is not a valid filter for {self.kind!r} ({', '.join(self.filters)})."
        super().__init__(self.message)


class InfrahubTransformNotFoundError(Error):
    def __init__(self, name: str, message: Optional[str] = None):
        self.message = message or f"The requested InfrahubTransform '{name}' was not found."
        super().__init__(self.message)


class ValidationError(Error):
    def __init__(self, identifier: str, message: str):
        self.identifier = identifier
        self.message = message
        super().__init__(self.message)


class AuthenticationError(Error):
    def __init__(self, message: Optional[str] = None):
        self.message = message or "Authentication Error, unable to execute the query."
        super().__init__(self.message)


class FeatureNotSupported(Error):
    """Raised when trying to use a method on a node that doesn't support it."""
