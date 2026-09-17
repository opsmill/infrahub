"""Behaviour of the generator that renders the SDK's error bindings.

CI regenerates the artefact and diffs it, which proves the committed file matches what the generator
produces from today's catalogue. It cannot prove the derivations are right, because a wrong rule
produces the same wrong file on both sides of that diff, and it never exercises a malformed catalogue
at all. These cover the rules and the refusals.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.errors.sdk_bindings import (
    BindingsState,
    ErrorCatalogueGenerationError,
    build_bindings_context,
    classify_bindings_state,
    derive_exception_name,
    dunder_all_sort_key,
    load_catalogue,
    payload_fields,
    python_type,
    scan_sdk_exceptions,
    validate_catalogue,
)

if TYPE_CHECKING:
    from collections.abc import Callable

REPO_ROOT = Path(__file__).resolve().parents[4]
SDK_BASE = REPO_ROOT / "python_sdk" / "infrahub_sdk" / "exceptions" / "base.py"
CATALOGUE_PATH = REPO_ROOT / "schema" / "error-catalogue.json"


@pytest.fixture(scope="module")
def catalogue() -> dict[str, Any]:
    return load_catalogue(CATALOGUE_PATH)


@pytest.fixture(scope="module")
def sdk_exceptions() -> tuple[dict[str, str], set[str]]:
    return scan_sdk_exceptions(SDK_BASE)


@pytest.fixture
def build(catalogue: dict[str, Any], sdk_exceptions: tuple[dict[str, str], set[str]]) -> Callable[..., dict[str, Any]]:
    """Build the render context from a mutated copy of the real catalogue."""
    default_adopted, defined = sdk_exceptions

    def _build(
        mutate: Callable[[dict[str, Any]], None] | None = None, adopted: dict[str, str] | None = None
    ) -> dict[str, Any]:
        working = copy.deepcopy(catalogue)
        if mutate is not None:
            mutate(working)
        return build_bindings_context(working, adopted or default_adopted, defined)

    return _build


# --------------------------------------------------------------------------------------------------
# Name derivation and the JSON Schema vocabulary
# --------------------------------------------------------------------------------------------------


@dataclass
class NameCase:
    name: str
    code: str
    expected: str


@pytest.mark.parametrize(
    "case",
    [
        NameCase(name="already-ends-in-error", code="UNDEFINED_ERROR", expected="UndefinedError"),
        NameCase(name="suffix-appended", code="NODE_NOT_FOUND", expected="NodeNotFoundError"),
        NameCase(name="multi-word", code="UNIQUENESS_VIOLATION", expected="UniquenessViolationError"),
        NameCase(name="preposition", code="MERGE_IN_PROGRESS", expected="MergeInProgressError"),
    ],
    ids=lambda case: case.name,
)
def test_exception_name_appends_error_only_when_absent(case: NameCase) -> None:
    assert derive_exception_name(case.code) == case.expected


@dataclass
class TypeCase:
    name: str
    schema: dict[str, Any]
    expected: str


@pytest.mark.parametrize(
    "case",
    [
        TypeCase(name="string", schema={"type": "string"}, expected="str"),
        TypeCase(name="datetime", schema={"type": "string", "format": "date-time"}, expected="datetime"),
        TypeCase(name="integer", schema={"type": "integer"}, expected="int"),
        TypeCase(name="number", schema={"type": "number"}, expected="float"),
        TypeCase(name="boolean", schema={"type": "boolean"}, expected="bool"),
        TypeCase(name="array", schema={"type": "array", "items": {"type": "string"}}, expected="list[str]"),
        TypeCase(name="array-of-int", schema={"type": "array", "items": {"type": "integer"}}, expected="list[int]"),
        TypeCase(name="nullable", schema={"anyOf": [{"type": "string"}, {"type": "null"}]}, expected="str | None"),
        TypeCase(
            name="nullable-datetime",
            schema={"anyOf": [{"type": "string", "format": "date-time"}, {"type": "null"}]},
            expected="datetime | None",
        ),
        TypeCase(
            name="array-of-nullable",
            schema={"type": "array", "items": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
            expected="list[str | None]",
        ),
    ],
    ids=lambda case: case.name,
)
def test_supported_schema_fragments_map_to_their_python_type(case: TypeCase) -> None:
    assert python_type(case.schema, "SOME_CODE") == case.expected


@dataclass
class FragmentCase:
    name: str
    schema: dict[str, Any]


@pytest.mark.parametrize(
    "case",
    [
        FragmentCase(name="nested-object", schema={"type": "object", "properties": {"inner": {"type": "string"}}}),
        FragmentCase(name="ref", schema={"$ref": "#/definitions/Thing"}),
        FragmentCase(name="array-without-items", schema={"type": "array"}),
        FragmentCase(name="unknown-type", schema={"type": "decimal"}),
        FragmentCase(name="list-form-type", schema={"type": ["string", "null"]}),
        FragmentCase(name="enum", schema={"enum": ["a", "b"]}),
        FragmentCase(name="empty-anyof", schema={"anyOf": []}),
    ],
    ids=lambda case: case.name,
)
def test_unsupported_schema_fragment_aborts_naming_the_fragment(case: FragmentCase) -> None:
    with pytest.raises(
        ErrorCatalogueGenerationError,
        match=r'^Catalogue code "SOME_CODE" uses a JSON Schema construct the generator does not support: .+',
    ):
        python_type(case.schema, "SOME_CODE")


def test_required_field_carries_no_default_and_optional_field_carries_its_own() -> None:
    fields = payload_fields(
        {
            "properties": {
                "kept": {"type": "string"},
                "nullable": {"anyOf": [{"type": "string"}, {"type": "null"}], "default": None},
                "defaulted": {"type": "string", "default": "all"},
            },
            "required": ["kept"],
        },
        "SOME_CODE",
    )

    assert fields == [
        {"name": "kept", "type": "str", "default": None},
        {"name": "nullable", "type": "str | None", "default": "None"},
        # Not required is not the same as nullable: a declared default keeps the type it declares.
        {"name": "defaulted", "type": "str", "default": "'all'"},
    ]


# --------------------------------------------------------------------------------------------------
# Adoption, discovered by parsing the SDK rather than importing it
# --------------------------------------------------------------------------------------------------


def test_adoption_reads_declared_codes_and_ignores_inherited_ones(
    sdk_exceptions: tuple[dict[str, str], set[str]],
) -> None:
    adopted, defined = sdk_exceptions

    assert adopted == {
        "BRANCH_NOT_FOUND": "BranchNotFoundError",
        "NODE_NOT_FOUND": "NodeNotFoundError",
        "SCHEMA_NOT_FOUND": "SchemaNotFoundError",
    }
    # It subclasses an adopted class and clears CODE, so it represents no code of its own.
    assert "NodeInvalidError" not in adopted.values()
    assert {"NodeInvalidError", "GraphQLError", "ApiError", "UNDEFINED_ERROR_CODE"} <= defined


def test_adoption_walk_reads_both_annotated_and_plain_assignments(tmp_path: Path) -> None:
    source = tmp_path / "base.py"
    source.write_text(
        "from typing import ClassVar\n\n"
        "class Annotated:\n    CODE: ClassVar[str | None] = 'ANNOTATED'\n\n"
        "class Plain:\n    CODE = 'PLAIN'\n\n"
        "class Disclaimed(Annotated):\n    CODE: ClassVar[str | None] = None\n\n"
        "def factory():\n    class Nested:\n        CODE = 'NESTED'\n    return Nested\n",
        encoding="utf-8",
    )

    adopted, defined = scan_sdk_exceptions(source)

    assert adopted == {"ANNOTATED": "Annotated", "PLAIN": "Plain"}
    # A class defined inside a function binds no module-level name and adopts nothing.
    assert defined == {"Annotated", "Plain", "Disclaimed"}


def test_two_classes_declaring_one_code_aborts(tmp_path: Path) -> None:
    source = tmp_path / "base.py"
    source.write_text("class A:\n    CODE = 'X'\n\nclass B:\n    CODE = 'X'\n", encoding="utf-8")

    with pytest.raises(
        ErrorCatalogueGenerationError,
        match=r'^infrahub_sdk/exceptions/base\.py declares CODE = "X" on both A and B\. '
        r"A code can be adopted by one class\.$",
    ):
        scan_sdk_exceptions(source)


def test_unreadable_sdk_module_names_the_submodule_remedy(tmp_path: Path) -> None:
    with pytest.raises(ErrorCatalogueGenerationError, match=r"git submodule update --init python_sdk"):
        scan_sdk_exceptions(tmp_path / "does-not-exist.py")


# --------------------------------------------------------------------------------------------------
# What the real catalogue produces
# --------------------------------------------------------------------------------------------------


def test_real_catalogue_emits_a_class_per_code_the_sdk_does_not_own(
    build: Callable[..., dict[str, Any]], catalogue: dict[str, Any]
) -> None:
    context = build()
    transport_owned = {code for code, entry in catalogue["codes"].items() if entry["http_status"] in {401, 403}}
    dispatched = {code for code, _ in context["code_to_exception"]}

    assert {model["code"] for model in context["payload_models"]} == set(catalogue["codes"])
    assert dispatched == set(catalogue["codes"]) - transport_owned
    assert {entry["name"] for entry in context["exception_classes"]}.isdisjoint(
        {"NodeNotFoundError", "BranchNotFoundError", "SchemaNotFoundError"}
    )
    assert {entry["parent"] for entry in context["exception_classes"]} == {"GraphQLError"}


def test_every_dispatchable_code_has_a_builder(build: Callable[..., dict[str, Any]]) -> None:
    context = build()

    assert [builder["code"] for builder in context["builders"]] == [code for code, _ in context["code_to_exception"]]
    assert [builder["name"] for builder in context["builders"]] == [
        f"_build_{code.lower()}" for code, _ in context["code_to_exception"]
    ]


def test_codes_are_emitted_in_sorted_order(build: Callable[..., dict[str, Any]]) -> None:
    codes = [code for code, _ in build()["code_to_data_model"]]

    assert codes == sorted(codes), "reordering the catalogue JSON must not churn the diff"


def test_dunder_all_orders_constants_then_classes_then_functions() -> None:
    names = ["exception_from_payload", "Code10Data", "Code2Data", "CODE_TO_EXCEPTION", "UndefinedError"]

    assert sorted(names, key=dunder_all_sort_key) == [
        "CODE_TO_EXCEPTION",
        "Code2Data",
        "Code10Data",
        "UndefinedError",
        "exception_from_payload",
    ]


def test_generator_reads_the_committed_catalogue_artefact(catalogue: dict[str, Any]) -> None:
    assert catalogue == json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------------------
# Refusals: the generator emits no guess
# --------------------------------------------------------------------------------------------------


@dataclass
class RootCase:
    name: str
    payload: Any
    match: str


@pytest.mark.parametrize(
    "case",
    [
        RootCase(name="non-object-root", payload=["not", "an", "object"], match=r"root must be an object\.$"),
        RootCase(
            name="codes-missing",
            payload={"infrahub_catalogue_version": "1"},
            match=r"must contain a `codes` object\.$",
        ),
        RootCase(
            name="codes-empty",
            payload={"infrahub_catalogue_version": "1", "codes": {}},
            match=r"`codes` is empty\.$",
        ),
        RootCase(name="version-missing", payload={"codes": {"X": {}}}, match=r"infrahub_catalogue_version"),
        RootCase(
            name="version-blank",
            payload={"infrahub_catalogue_version": "  ", "codes": {"X": {}}},
            match=r"infrahub_catalogue_version",
        ),
    ],
    ids=lambda case: case.name,
)
def test_malformed_catalogue_root_aborts(case: RootCase) -> None:
    with pytest.raises(ErrorCatalogueGenerationError, match=case.match):
        validate_catalogue(case.payload)


def test_unreadable_catalogue_names_the_export_command(tmp_path: Path) -> None:
    with pytest.raises(ErrorCatalogueGenerationError, match=r"uv run invoke backend\.export-error-catalogue"):
        load_catalogue(tmp_path / "missing.json")


def test_catalogue_that_is_not_json_aborts(tmp_path: Path) -> None:
    source = tmp_path / "error-catalogue.json"
    source.write_text("{not json", encoding="utf-8")

    with pytest.raises(ErrorCatalogueGenerationError, match=r"is not valid JSON"):
        load_catalogue(source)


_ABSENT = object()


def _replace(field_name: str, value: Any) -> Callable[[dict[str, Any]], None]:
    """Replace one member of a real catalogue entry, or drop it when the value is the sentinel."""

    def mutate(working: dict[str, Any]) -> None:
        entry = working["codes"]["UNIQUENESS_VIOLATION"]
        if value is _ABSENT:
            entry.pop(field_name, None)
        else:
            entry[field_name] = value

    return mutate


@dataclass
class EntryCase:
    name: str
    mutate: Callable[[dict[str, Any]], None]
    match: str


@pytest.mark.parametrize(
    "case",
    [
        EntryCase(
            name="status-missing",
            mutate=_replace("http_status", _ABSENT),
            match=r"must declare an integer `http_status`",
        ),
        EntryCase(
            name="status-not-int", mutate=_replace("http_status", "422"), match=r"must declare an integer `http_status`"
        ),
        EntryCase(
            name="status-is-bool", mutate=_replace("http_status", True), match=r"must declare an integer `http_status`"
        ),
        EntryCase(
            name="schema-missing", mutate=_replace("data_schema", _ABSENT), match=r"must declare a `data_schema` object"
        ),
        EntryCase(
            name="title-missing",
            mutate=_replace("data_schema", {"type": "object", "properties": {}}),
            match=r"must declare a non-empty `data_schema\.title`",
        ),
        EntryCase(
            name="title-empty",
            mutate=_replace("data_schema", {"type": "object", "title": "", "properties": {}}),
            match=r"must declare a non-empty `data_schema\.title`",
        ),
        EntryCase(
            name="description-quote",
            mutate=_replace("description", 'a """ quote'),
            match=r"would break the generated docstring",
        ),
        EntryCase(
            name="description-backslash",
            mutate=_replace("description", "a \\d backslash"),
            match=r"would break the generated docstring",
        ),
    ],
    ids=lambda case: case.name,
)
def test_malformed_entry_aborts(build: Callable[..., dict[str, Any]], case: EntryCase) -> None:
    with pytest.raises(ErrorCatalogueGenerationError, match=case.match):
        build(case.mutate)


@pytest.mark.parametrize(
    "field_name", ["code", "http_status", "message", "errors", "query", "variables", "model_config", "self"]
)
def test_payload_field_colliding_with_an_exception_member_aborts(
    build: Callable[..., dict[str, Any]], field_name: str
) -> None:
    def mutate(working: dict[str, Any]) -> None:
        schema = working["codes"]["UNIQUENESS_VIOLATION"]["data_schema"]
        schema["properties"][field_name] = {"title": field_name, "type": "string"}
        schema["required"].append(field_name)

    with pytest.raises(
        ErrorCatalogueGenerationError,
        match=rf"declares payload field\(s\) \['{field_name}'\], which the generated exception already binds",
    ):
        build(mutate)


@pytest.mark.parametrize("title", ["BaseModel", "ConfigDict", "datetime", "Any", "Self", "ClassVar"])
def test_payload_model_shadowing_a_module_import_aborts(build: Callable[..., dict[str, Any]], title: str) -> None:
    with pytest.raises(
        ErrorCatalogueGenerationError,
        match=rf'emits the name "{title}", which the generated module already binds',
    ):
        build(_replace("data_schema", {"type": "object", "title": title, "properties": {}}))


@pytest.mark.parametrize(
    "existing",
    ["ValidationError", "RateLimitError", "InvalidResponseError", "FileNotValidError", "ResourceNotDefinedError"],
)
def test_derived_name_colliding_with_a_hand_written_class_aborts(
    build: Callable[..., dict[str, Any]], existing: str
) -> None:
    code = "".join(f"_{char}" if char.isupper() else char.upper() for char in existing).lstrip("_")
    assert derive_exception_name(code) == existing

    def mutate(working: dict[str, Any]) -> None:
        entry = copy.deepcopy(working["codes"]["UNIQUENESS_VIOLATION"])
        entry["data_schema"]["title"] = f"{existing}Data"
        working["codes"][code] = entry

    with pytest.raises(
        ErrorCatalogueGenerationError,
        match=rf'derives the class name "{existing}", which .+ already defines without declaring that code',
    ):
        build(mutate)


def test_collision_is_cleared_by_adopting_the_code(
    build: Callable[..., dict[str, Any]], sdk_exceptions: tuple[dict[str, str], set[str]]
) -> None:
    adopted, _ = sdk_exceptions

    def mutate(working: dict[str, Any]) -> None:
        entry = copy.deepcopy(working["codes"]["UNIQUENESS_VIOLATION"])
        entry["data_schema"]["title"] = "RateLimitData"
        working["codes"]["RATE_LIMIT"] = entry

    context = build(mutate, adopted={**adopted, "RATE_LIMIT": "RateLimitError"})

    assert dict(context["code_to_exception"])["RATE_LIMIT"] == "RateLimitError"
    assert "RateLimitError" in context["base_imports"]


def test_adopting_a_transport_owned_code_aborts(
    build: Callable[..., dict[str, Any]], sdk_exceptions: tuple[dict[str, str], set[str]]
) -> None:
    """Adoption must not put a 401/403 code back in the lookup: the response decides those."""
    adopted, _ = sdk_exceptions

    with pytest.raises(
        ErrorCatalogueGenerationError,
        match=r'adopts "PERMISSION_DENIED" on PermissionDeniedError, but the catalogue gives it HTTP 403, '
        r"which the SDK resolves from the response instead",
    ):
        build(adopted={**adopted, "PERMISSION_DENIED": "PermissionDeniedError"})


def test_required_naming_an_absent_property_aborts(build: Callable[..., dict[str, Any]]) -> None:
    def mutate(working: dict[str, Any]) -> None:
        working["codes"]["UNIQUENESS_VIOLATION"]["data_schema"]["required"].append("ghost")

    with pytest.raises(
        ErrorCatalogueGenerationError, match=r"marks \['ghost'\] required, but declares no such property"
    ):
        build(mutate)


@dataclass
class SchemaMemberCase:
    name: str
    key: str
    value: Any


@pytest.mark.parametrize(
    "case",
    [
        SchemaMemberCase(name="properties-as-list", key="properties", value=[]),
        SchemaMemberCase(name="required-as-int", key="required", value=0),
    ],
    ids=lambda case: case.name,
)
def test_schema_members_of_the_wrong_type_abort(build: Callable[..., dict[str, Any]], case: SchemaMemberCase) -> None:
    def mutate(working: dict[str, Any]) -> None:
        working["codes"]["UNIQUENESS_VIOLATION"]["data_schema"][case.key] = case.value

    with pytest.raises(
        ErrorCatalogueGenerationError,
        match=r"must declare `data_schema\.properties` as an object and `data_schema\.required` as a list",
    ):
        build(mutate)


def test_two_codes_emitting_one_name_abort(build: Callable[..., dict[str, Any]]) -> None:
    def mutate(working: dict[str, Any]) -> None:
        working["codes"]["ANOTHER_CODE"] = copy.deepcopy(working["codes"]["UNIQUENESS_VIOLATION"])

    with pytest.raises(
        ErrorCatalogueGenerationError,
        match=r'^Catalogue codes "ANOTHER_CODE" and "UNIQUENESS_VIOLATION" both emit the name '
        r'"UniquenessViolationData"\.$',
    ):
        build(mutate)


# --------------------------------------------------------------------------------------------------
# The staleness gate's decision
# --------------------------------------------------------------------------------------------------


@dataclass
class StateCase:
    name: str
    tracked_at_head: bool
    working_tree_differs: bool
    expected: BindingsState


@pytest.mark.parametrize(
    "case",
    [
        StateCase(
            name="never-committed",
            tracked_at_head=False,
            working_tree_differs=True,
            expected=BindingsState.NOT_COMMITTED,
        ),
        StateCase(
            name="never-committed-and-clean",
            tracked_at_head=False,
            working_tree_differs=False,
            expected=BindingsState.NOT_COMMITTED,
        ),
        StateCase(
            name="committed-and-stale", tracked_at_head=True, working_tree_differs=True, expected=BindingsState.STALE
        ),
        StateCase(
            name="committed-and-fresh",
            tracked_at_head=True,
            working_tree_differs=False,
            expected=BindingsState.UP_TO_DATE,
        ),
    ],
    ids=lambda case: case.name,
)
def test_bindings_state_distinguishes_uncommitted_from_stale(case: StateCase) -> None:
    """An untracked artefact must not read as clean: `git diff` reports nothing for one."""
    state = classify_bindings_state(
        tracked_at_head=case.tracked_at_head, working_tree_differs=case.working_tree_differs
    )

    assert state is case.expected
