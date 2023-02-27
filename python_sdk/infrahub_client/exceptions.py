from __future__ import annotations

from typing import List, Optional


class Error(Exception):
    pass


class ServerNotReacheableError(Error):
    def __init__(self, address, message=None):
        self.address = address
        self.message = message or f"Unable to connect to '{address}'."
        super().__init__(self.message)


class ServerNotResponsiveError(Error):
    def __init__(self, url, message=None):
        self.url = url
        self.message = message or f"Unable to read from '{url}'."
        super().__init__(self.message)


class GraphQLError(Error):
    def __init__(self, errors: List[str], query: Optional[str] = None, variables: Optional[dict] = None):
        self.query = query
        self.variables = variables
        self.errors = errors
        self.message = f"An error occured while executing the GraphQL Query {self.query}, {self.errors}"
        super().__init__(self.message)


class BranchNotFound(Error):
    def __init__(self, identifier, message=None):
        self.identifier = identifier
        self.message = message or f"Unable to find the branch '{identifier}' in the Database."
        super().__init__(self.message)


class SchemaNotFound(Error):
    def __init__(self, identifier, message=None):
        self.identifier = identifier
        self.message = message or f"Unable to find the schema '{identifier}'."
        super().__init__(self.message)


class NodeNotFound(Error):
    def __init__(self, branch_name, node_type, identifier, message="Unable to find the node in the database."):
        self.branch_name = branch_name
        self.node_type = node_type
        self.identifier = identifier

        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"""
        {self.message}
        {self.branch_name} | {self.node_type} | {self.identifier}
        """


class FilterNotFound(Error):
    def __init__(self, identifier, kind, message=None):
        self.identifier = identifier
        self.kind = kind
        self.message = message or f"{identifier!r} is not a valid filter for {self.identifier!r}."
        super().__init__(self.message)
