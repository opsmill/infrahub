class Error(Exception):
    pass


class DatabaseError(Error):
    pass


class RepositoryError(Error):
    def __init__(self, identifier, message=None):
        self.identifier = identifier
        self.message = message or f"An error occured with GitRepository '{identifier}'."
        super().__init__(self.message)


class FileNotFound(Error):
    def __init__(self, repository_name, location, commit, message=None):
        self.repository_name = repository_name
        self.location = location
        self.commit = commit
        self.message = message or f"Unable to find the file at '{repository_name}::{commit}::{location}'."
        super().__init__(self.message)


class TransformError(Error):
    def __init__(self, repository_name, location, commit, message=None):
        self.repository_name = repository_name
        self.location = location
        self.commit = commit
        self.message = (
            message or f"An error occured with the transform function at '{repository_name}::{commit}::{location}'."
        )
        super().__init__(self.message)


class CheckError(Error):
    def __init__(self, repository_name, location, class_name, commit, message=None):
        self.repository_name = repository_name
        self.location = location
        self.commit = commit
        self.class_name = class_name
        self.message = (
            message
            or f"An error occured with the check function at '{repository_name}::{commit}::{location}::{class_name}'."
        )
        super().__init__(self.message)


class TransformNotFoundError(TransformError):
    def __init__(self, repository_name, location, commit, message=None):
        self.message = (
            message or f"Unable to locate the transform function at '{repository_name}::{commit}::{location}'."
        )
        super().__init__(repository_name, location, commit, self.message)


class BranchNotFound(Error):
    def __init__(self, identifier, message=None):
        self.identifier = identifier
        self.message = message or f"Unable to find the branch '{identifier}' in the Database."
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


class QueryError(Error):
    def __init__(self, query, params, message="Unable to execute the CYPHER query."):
        self.query = query
        self.params = params

        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f"""
        {self.message}
        {self.query}
        {self.params}
        """


class ValidationError(Error):
    def __init__(self, input_value):

        self.message = None
        self.location = None
        self.messages = {}

        if isinstance(input_value, str):
            self.message = input_value
        elif isinstance(input_value, dict) and len(input_value) == 1:
            self.message = list(input_value.values())[0]
            self.location = list(input_value.keys())[0]
        elif isinstance(input_value, dict) and len(input_value) > 1:
            for key, value in input_value.items():
                self.messages[key] = value

        elif isinstance(input_value, list):
            for item in input_value:
                if isinstance(item, self.__class__):
                    self.messages[item.location] = item.message
                elif isinstance(item, dict):
                    for key, value in item.items():
                        self.messages[key] = value

        super().__init__(self.message)

    def __str__(self):
        if self.messages:
            return ", ".join([f"{message} at {location}" for location, message in self.messages.items()])

        return f"{self.message} at {self.location or '<Undefined>'}"
