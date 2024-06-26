from rich.syntax import Syntax
from rich.traceback import Frame, Traceback


class Error(Exception):
    """pytest-infrahub Base exception."""


class InvalidResourceConfigError(Error):
    def __init__(self, resource_name: str):
        super().__init__(f"Improperly configured resource with name '{resource_name}'.")


class DirectoryNotFoundError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Unable to find directory {name!r}."
        super().__init__(self.message)


class FileNotValidError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Unable to access file {name!r}."
        super().__init__(self.message)


class OutputMatchError(Error):
    def __init__(self, name: str, message: str = "", differences: str = ""):
        self.message = message or f"Rendered output does not match expected output for {name!r}."
        self.differences = differences
        super().__init__(self.message)


class Jinja2TransformError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Unexpected error happened while processing {name!r}."
        super().__init__(self.message)


class Jinja2TransformUndefinedError(Error):
    def __init__(self, name: str, rtb: Traceback, errors: list[tuple[Frame, Syntax]], message: str = ""):
        self.rtb = rtb
        self.errors = errors
        self.message = message or f"Unable to render Jinja2 transform {name!r}."
        super().__init__(self.message)


class CheckDefinitionError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Check {name!r} is not properly defined."
        super().__init__(self.message)


class CheckResultError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Unexpected result for check {name!r}."
        super().__init__(self.message)


class PythonTransformDefinitionError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Python transform {name!r} is not properly defined."
        super().__init__(self.message)
