class Error(Exception):
    pass


class DatabaseError(Error):
    pass


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
    def __init__(self, input):

        self.message = None
        self.location = None
        self.messages = {}

        if isinstance(input, str):
            self.message = input
        elif isinstance(input, dict) and len(input) == 1:
            self.message = list(input.values())[0]
            self.location = list(input.keys())[0]
        elif isinstance(input, dict) and len(input) > 1:
            for key, value in input.items():
                self.messages[key] = value

        elif isinstance(input, list):
            for item in input:
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
