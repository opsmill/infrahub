class Error(Exception):
    """Infrahub CTL Base exception."""


class QueryNotFoundError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"The requested query '{name}' was not found."
        super().__init__(self.message)
