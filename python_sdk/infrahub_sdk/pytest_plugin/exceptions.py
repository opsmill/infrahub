from typing import List, Tuple

from rich.syntax import Syntax
from rich.traceback import Frame, Traceback


class Error(Exception):
    """pytest-infrahub Base exception."""


class DirectoryNotFoundError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Unable to find directory {name!r}."
        super().__init__(self.message)


class FileNotValidError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Unable to access file {name!r}."
        super().__init__(self.message)


class Jinja2TransformException(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Unexpected error happened while processing {name!r}."
        super().__init__(self.message)


class Jinja2TransformUndefinedError(Error):
    def __init__(self, name: str, rtb: Traceback, errors: List[Tuple[Frame, Syntax]], message: str = ""):
        self.rtb = rtb
        self.errors = errors
        self.message = message or f"Unable to render Jinja2 transform {name!r}."
        super().__init__(self.message)


class PythonTransformDefinitionError(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Python transform {name!r} is not properly defined.."
        super().__init__(self.message)


class PythonTransformException(Error):
    def __init__(self, name: str, message: str = ""):
        self.message = message or f"Unexpected error happened while processing Python transform {name!r}."
        super().__init__(self.message)
