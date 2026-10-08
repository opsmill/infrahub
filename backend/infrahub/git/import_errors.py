from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from infrahub_sdk.exceptions import (
    FileNotValidError,
    GraphQLError,
    GraphQLQueryError,
    ModuleImportError,
    ObjectValidationError,
    ValidationError,
)
from infrahub_sdk.exceptions import RepositoryFileNotFoundError as SdkRepositoryFileNotFoundError
from prefect.logging import get_run_logger
from pydantic import ValidationError as PydanticValidationError

from infrahub.exceptions import CommitNotFoundError, RepositoryError
from infrahub.log import suppress_traceback_in_logs

if TYPE_CHECKING:
    from collections.abc import Iterator


@suppress_traceback_in_logs
class RepositoryImportError(RepositoryError):
    """Raised when the import of a branch's objects failed, carrying the message the import logged.

    Registered so the logging layer drops the traceback Prefect writes when it leaves a flow: the
    import already logged the failure once, as a readable message or with its traceback.
    """

    def __init__(self, identifier: str, branch_name: str, message: str) -> None:
        super().__init__(identifier=identifier, message=message)
        self.branch_name = branch_name


def log_import_failure(identifier: str, branch_name: str, exc: Exception) -> RepositoryImportError:
    """Log a failed import once, with its traceback only when the failure is not recognised.

    Returns the failure as an error carrying the logged message, for the caller to raise or record.
    """
    log = get_run_logger()
    description = describe_import_error(exc)
    recognised = description is not None
    if description is None:
        description = prefix_with_notes(exc=exc, description=f"{type(exc).__name__}: {exc}")
    # Discrete fields let log shippers and alert rules filter on a failed import without parsing the message.
    log.error(
        f"Failed to import branch '{branch_name}': {description}",
        exc_info=None if recognised else exc,
        extra={"repository": identifier, "branch": branch_name, "step": "import", "reason": description},
    )
    return RepositoryImportError(identifier=identifier, branch_name=branch_name, message=description)


def describe_import_error(exc: BaseException) -> str | None:
    """Return a readable message for an expected import failure, or None for an exception it does not recognise.

    The notes added to the exception, which name the `.infrahub.yml` entry being imported, prefix the
    message. The SDK `Error` base class is not recognised, because it also covers connection errors;
    `GraphQLQueryError` is, because it covers only the rendering of a query from the repository's files.
    """
    match exc:
        case ValidationError():
            # The string form starts with the identifier, which is the repository ID for some callers.
            description = "; ".join(exc.messages) if exc.messages else (exc.message or "")
        case GraphQLError() if exc.errors:
            description = "; ".join(str(error.get("message", error)) for error in exc.errors)
        case ModuleImportError(__cause__=SyntaxError() as syntax_error):
            description = _describe_syntax_error(syntax_error)
        case (
            ModuleImportError()
            | ModuleNotFoundError()
            | SdkRepositoryFileNotFoundError()
            | FileNotValidError()
            | GraphQLQueryError()
            | ObjectValidationError()
        ):
            description = str(exc)
        case SyntaxError():
            description = _describe_syntax_error(exc)
        case PydanticValidationError():
            details = "; ".join(
                f"{'/'.join(str(location) for location in error['loc'])} | {error['msg']} ({error['type']})"
                for error in exc.errors()
            )
            description = f"{exc.title}: {details}"
        case RepositoryError() | CommitNotFoundError():
            description = exc.message
        case _:
            return None
    return prefix_with_notes(exc=exc, description=description)


def _describe_syntax_error(exc: SyntaxError) -> str:
    # The string form names only the base name of the file, which is ambiguous for a helper module.
    if exc.filename is None:
        return f"Syntax error: {exc.msg}"
    return f"Syntax error in {exc.filename}, line {exc.lineno}: {exc.msg}"


def prefix_with_notes(exc: BaseException, description: str) -> str:
    """Prefix the description with the notes added to the exception, outermost context first."""
    return ": ".join([*reversed(getattr(exc, "__notes__", [])), description])


@contextmanager
def import_entry(label: str, worktree_directory: Path | None = None) -> Iterator[None]:
    """Add the label of the `.infrahub.yml` entry being imported as a note to any exception raised inside.

    With a worktree directory, the file of a syntax error raised inside is rewritten relative to it,
    so the message names the file as it is in the repository rather than in the worktree.
    """
    try:
        yield
    except Exception as exc:
        if worktree_directory is not None:
            _make_syntax_error_path_relative(exc=exc, worktree_directory=worktree_directory)
        exc.add_note(label)
        raise


def _make_syntax_error_path_relative(exc: Exception, worktree_directory: Path) -> None:
    syntax_error = exc.__cause__ if isinstance(exc, ModuleImportError) else exc
    if not isinstance(syntax_error, SyntaxError) or syntax_error.filename is None:
        return
    filename = Path(syntax_error.filename)
    if filename.is_relative_to(worktree_directory):
        syntax_error.filename = str(filename.relative_to(worktree_directory))
