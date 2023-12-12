class Error(Exception):
    """Infrahub CTL Base exception."""


class QueryNotFoundError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"The requested query '{name}' was not found."
        super().__init__(self.message)


class InfrahubTransformNotFoundError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"The requested InfrahubTransform '{name}' was not found."
        super().__init__(self.message)


class FileNotValidError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Unable to access the file '{name}'."
        super().__init__(self.message)
