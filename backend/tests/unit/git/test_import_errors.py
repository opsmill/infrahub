from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import (
    CircularFragmentError,
    DuplicateFragmentError,
    FileNotValidError,
    FragmentFileNotFoundError,
    FragmentNotFoundError,
    GraphQLError,
    ModuleImportError,
    NodeNotFoundError,
    ObjectValidationError,
    QuerySyntaxError,
    ServerNotReachableError,
    ValidationError,
)
from infrahub_sdk.exceptions import Error as SdkError
from infrahub_sdk.exceptions import RepositoryFileNotFoundError as SdkRepositoryFileNotFoundError
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from infrahub.exceptions import CommitNotFoundError, RepositoryConfigurationError
from infrahub.git.import_errors import describe_import_error, import_entry

if TYPE_CHECKING:
    from collections.abc import Callable

UNIQUENESS_QUERY = """
mutation ($value_18724e16673987e53297c5137afc20ec: String!) {
    CoreGraphQLQueryCreate(data: {name: {value: "backbone_service"}}) { ok }
}
"""


class _Entry(BaseModel):
    name: str


def _pydantic_error() -> PydanticValidationError:
    try:
        _Entry.model_validate({})
    except PydanticValidationError as exc:
        return exc
    raise AssertionError("The model accepted an empty payload")


def _with_notes(exc: Exception, *notes: str) -> Exception:
    for note in notes:
        exc.add_note(note)
    return exc


def _caused_by(exc: Exception, cause: Exception) -> Exception:
    exc.__cause__ = cause
    return exc


@dataclass
class DescribedCase:
    name: str
    error: BaseException
    expected: str


DESCRIBED_CASES = [
    DescribedCase(
        name="sdk_validation_error_message_without_identifier",
        error=ValidationError(identifier="18724e15-38ed-4bc5-32fb-c51a00d32704", message="Schema not valid"),
        expected="Schema not valid",
    ),
    DescribedCase(
        name="sdk_validation_error_messages",
        error=ValidationError(identifier="objects/devices.yml", messages=["0.name: missing", "1.role: missing"]),
        expected="0.name: missing; 1.role: missing",
    ),
    DescribedCase(
        name="sdk_validation_error_without_message",
        error=ValidationError(identifier="schema.yml"),
        expected="Validation Error for schema.yml",
    ),
    DescribedCase(
        name="graphql_error_without_query_text",
        error=GraphQLError(
            errors=[
                {
                    "message": "Violates uniqueness constraint 'name'",
                    "locations": [{"line": 3, "column": 5}],
                    "path": ["CoreGraphQLQueryCreate"],
                }
            ],
            query=UNIQUENESS_QUERY,
        ),
        expected="Violates uniqueness constraint 'name'",
    ),
    DescribedCase(
        name="graphql_error_with_several_errors",
        error=GraphQLError(errors=[{"message": "first"}, {"message": "second"}], query=UNIQUENESS_QUERY),
        expected="first; second",
    ),
    DescribedCase(
        name="graphql_error_entry_without_message",
        error=GraphQLError(errors=[{"path": ["CoreGraphQLQueryCreate"]}], query=UNIQUENESS_QUERY),
        expected="{'path': ['CoreGraphQLQueryCreate']}",
    ),
    DescribedCase(
        name="module_import_error_caused_by_module_not_found",
        error=_caused_by(
            ModuleImportError(message="No module named 'netutils' (generators/backbone.py)"),
            ModuleNotFoundError("No module named 'netutils'"),
        ),
        expected="No module named 'netutils' (generators/backbone.py)",
    ),
    DescribedCase(
        name="module_import_error",
        error=ModuleImportError(message="The specified class Missing was not found within the module"),
        expected="The specified class Missing was not found within the module",
    ),
    DescribedCase(
        name="module_not_found_error",
        error=ModuleNotFoundError("No module named 'netutils'", name="netutils"),
        expected="No module named 'netutils'",
    ),
    DescribedCase(
        name="sdk_repository_file_not_found",
        error=SdkRepositoryFileNotFoundError(file_path="queries/backbone.gql"),
        expected="File 'queries/backbone.gql' does not exist.",
    ),
    DescribedCase(
        name="file_not_valid",
        error=FileNotValidError(name="objects/devices.yml", message="objects/devices.yml does not exist!"),
        expected="objects/devices.yml does not exist!",
    ),
    DescribedCase(
        name="fragment_not_found",
        error=FragmentNotFoundError(fragment_name="interface_fields"),
        expected="Fragment 'interface_fields' not found.",
    ),
    DescribedCase(
        name="fragment_file_not_found",
        error=FragmentFileNotFoundError(file_path="fragments/interfaces.gql"),
        expected="Fragment file 'fragments/interfaces.gql' declared in graphql_fragments does not exist.",
    ),
    DescribedCase(
        name="query_syntax_error",
        error=QuerySyntaxError(syntax_error="Expected Name, found '}'."),
        expected="GraphQL syntax error: Expected Name, found '}'.",
    ),
    DescribedCase(
        name="duplicate_fragment",
        error=DuplicateFragmentError(fragment_name="interface_fields"),
        expected="Fragment 'interface_fields' is defined more than once across declared fragment files.",
    ),
    DescribedCase(
        name="circular_fragment",
        error=CircularFragmentError(cycle=["a", "b", "a"]),
        expected="Circular fragment dependency detected: a -> b -> a.",
    ),
    DescribedCase(
        name="syntax_error",
        error=SyntaxError("invalid syntax", ("transforms/helpers/utils.py", 3, 5, "def (", 3, 6)),
        expected="Syntax error in transforms/helpers/utils.py, line 3: invalid syntax",
    ),
    DescribedCase(
        name="syntax_error_without_file",
        error=SyntaxError("invalid syntax"),
        expected="Syntax error: invalid syntax",
    ),
    DescribedCase(
        name="module_import_error_caused_by_syntax_error",
        error=_caused_by(
            ModuleImportError(message="invalid syntax (utils.py, line 3)"),
            SyntaxError("invalid syntax", ("generators/utils.py", 3, 5, "def (", 3, 6)),
        ),
        expected="Syntax error in generators/utils.py, line 3: invalid syntax",
    ),
    DescribedCase(
        name="pydantic_validation_error",
        error=_pydantic_error(),
        expected="_Entry: name | Field required (missing)",
    ),
    DescribedCase(
        name="repository_error",
        error=RepositoryConfigurationError(
            identifier="demo", message="Repository 'demo' is missing a configuration file."
        ),
        expected="Repository 'demo' is missing a configuration file.",
    ),
    DescribedCase(
        name="commit_not_found",
        error=CommitNotFoundError(identifier="demo", commit="0123abc"),
        expected="Commit 0123abc not found with GitRepository 'demo'.",
    ),
    DescribedCase(
        name="object_validation_error",
        error=ObjectValidationError(position=["spec", "data", 0], message="Object is not valid - name is mandatory"),
        expected="spec.data.0: Object is not valid - name is mandatory",
    ),
    DescribedCase(
        name="graphql_error_with_entry_note",
        error=_with_notes(
            GraphQLError(errors=[{"message": "Violates uniqueness constraint 'name'"}], query=UNIQUENESS_QUERY),
            "GraphQL query 'backbone_service' (queries/backbone.gql)",
        ),
        expected="GraphQL query 'backbone_service' (queries/backbone.gql): Violates uniqueness constraint 'name'",
    ),
    DescribedCase(
        name="notes_outermost_first",
        error=_with_notes(ModuleNotFoundError("No module named 'netutils'"), "inner", "outer"),
        expected="outer: inner: No module named 'netutils'",
    ),
]


@pytest.mark.parametrize("case", DESCRIBED_CASES, ids=[case.name for case in DESCRIBED_CASES])
def test_describes_expected_import_error(case: DescribedCase) -> None:
    assert describe_import_error(case.error) == case.expected


@dataclass
class UnrecognisedCase:
    name: str
    error: BaseException


UNRECOGNISED_CASES = [
    UnrecognisedCase(name="value_error", error=ValueError("boom")),
    UnrecognisedCase(name="sdk_error", error=SdkError("Unexpected server response")),
    UnrecognisedCase(name="server_not_reachable", error=ServerNotReachableError(address="http://infrahub:8000")),
    UnrecognisedCase(name="graphql_error_without_server_errors", error=GraphQLError(errors=[], query=UNIQUENESS_QUERY)),
    UnrecognisedCase(
        name="node_not_found",
        error=NodeNotFoundError(identifier={"id": ["device_inventry"]}, node_type="CoreGraphQLQuery"),
    ),
    UnrecognisedCase(name="value_error_with_note", error=_with_notes(ValueError("boom"), "File 'objects/a.yml'")),
]


@pytest.mark.parametrize("case", UNRECOGNISED_CASES, ids=[case.name for case in UNRECOGNISED_CASES])
def test_does_not_describe_unrecognised_error(case: UnrecognisedCase) -> None:
    assert describe_import_error(case.error) is None


def test_import_entry_adds_the_label_as_a_note() -> None:
    # The match covers the notes, which pytest appends to the message on their own lines.
    with (
        pytest.raises(
            ModuleNotFoundError,
            match=r"^No module named 'netutils'\nPython transform 'interfaces' \(transforms/interfaces\.py\)$",
        ),
        import_entry("Python transform 'interfaces' (transforms/interfaces.py)"),
    ):
        raise ModuleNotFoundError("No module named 'netutils'")


def _raised_inside(label: str, worktree_directory: Path, source_file: Path) -> Exception:
    try:
        with import_entry(label, worktree_directory=worktree_directory):
            compile(source_file.read_text(encoding="utf-8"), str(source_file), "exec")
    except SyntaxError as exc:
        return exc
    raise AssertionError("The source compiled without a syntax error")


def test_import_entry_names_a_syntax_error_file_relative_to_the_worktree(tmp_path: Path) -> None:
    helper = tmp_path / "transforms" / "helpers" / "utils.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("x = = 1\n", encoding="utf-8")

    error = _raised_inside(
        label="Python transform 'interfaces' (transforms/interfaces.py)",
        worktree_directory=tmp_path,
        source_file=helper,
    )

    assert describe_import_error(error) == (
        "Python transform 'interfaces' (transforms/interfaces.py): "
        "Syntax error in transforms/helpers/utils.py, line 1: invalid syntax"
    )


WORKTREE = "/repositories/demo/commits/abc123"


def _syntax_error(filename: str | None) -> SyntaxError:
    if filename is None:
        return SyntaxError("invalid syntax")
    return SyntaxError("invalid syntax", (filename, 3, 5, "def (", 3, 6))


@dataclass
class WorktreePathCase:
    name: str
    # A factory, because the context manager adds a note to the exception and rewrites its file.
    make_error: Callable[[], Exception]
    expected: str


WORKTREE_PATH_CASES = [
    WorktreePathCase(
        name="syntax_error_inside_the_worktree",
        make_error=lambda: _syntax_error(f"{WORKTREE}/transforms/utils.py"),
        expected="Entry: Syntax error in transforms/utils.py, line 3: invalid syntax",
    ),
    WorktreePathCase(
        name="module_import_error_caused_by_syntax_error_inside_the_worktree",
        make_error=lambda: _caused_by(
            ModuleImportError(message="invalid syntax"), _syntax_error(f"{WORKTREE}/generators/x.py")
        ),
        expected="Entry: Syntax error in generators/x.py, line 3: invalid syntax",
    ),
    WorktreePathCase(
        name="syntax_error_outside_the_worktree",
        make_error=lambda: _syntax_error("/usr/lib/python3.14/site-packages/broken.py"),
        expected="Entry: Syntax error in /usr/lib/python3.14/site-packages/broken.py, line 3: invalid syntax",
    ),
    WorktreePathCase(
        name="syntax_error_without_file",
        make_error=lambda: _syntax_error(None),
        expected="Entry: Syntax error: invalid syntax",
    ),
    WorktreePathCase(
        name="module_import_error_without_cause",
        make_error=lambda: ModuleImportError(message="The specified class Missing was not found within the module"),
        expected="Entry: The specified class Missing was not found within the module",
    ),
    WorktreePathCase(
        name="other_error",
        make_error=lambda: ModuleNotFoundError("No module named 'netutils'"),
        expected="Entry: No module named 'netutils'",
    ),
]


def _raise_in_entry(error: Exception, worktree_directory: Path) -> Exception:
    try:
        with import_entry("Entry", worktree_directory=worktree_directory):
            raise error
    except Exception as exc:  # noqa: BLE001
        return exc


@pytest.mark.parametrize("case", WORKTREE_PATH_CASES, ids=[case.name for case in WORKTREE_PATH_CASES])
def test_import_entry_rewrites_only_syntax_error_files_inside_the_worktree(case: WorktreePathCase) -> None:
    error = case.make_error()

    raised = _raise_in_entry(error=error, worktree_directory=Path(WORKTREE))

    assert raised is error
    assert describe_import_error(raised) == case.expected
