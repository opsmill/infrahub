from infrahub.exceptions import Error


class QueryValidationError(Error):
    HTTP_CODE = 400

    def __init__(self, message: str):
        self.message = message


class SchemaNotValidError(Error):
    HTTP_CODE = 422

    def __init__(self, message: str):
        self.message = message
