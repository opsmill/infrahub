"""Render the Python SDK's error bindings from the published catalogue artefact.

The SDK holds no copy of the catalogue: Infrahub owns it and generates the bindings into the
submodule, the same way it generates the schema models and the protocols. Everything here derives
from the artefact alone, and anything it cannot derive aborts rather than emitting a guess.
"""

from __future__ import annotations

import ast
import json
import keyword
import re
import textwrap
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

CATALOGUE_SOURCE = "schema/error-catalogue.json"
SDK_EXCEPTIONS_BASE = "infrahub_sdk/exceptions/base.py"
SDK_ERROR_BINDINGS = "infrahub_sdk/exceptions/catalogue.py"
TEMPLATE_NAME = "generate_sdk_errors.j2"

# Codes with these statuses get a payload model but no generated class; the SDK routes them by the
# HTTP response it saw instead.
TRANSPORT_OWNED_STATUSES = frozenset({401, 403})

# Names the generated module binds for its own purposes. A payload field or model that took one of
# these would shadow it, so the catalogue has to rename rather than the generator guess.
GENERATED_MODULE_NAMES = frozenset(
    {
        "Any",
        "BaseModel",
        "CODE_TO_DATA_MODEL",
        "CODE_TO_EXCEPTION",
        "Callable",
        "ClassVar",
        "ConfigDict",
        "Mapping",
        "Self",
        "_CODE_TO_BUILDER",
        "annotations",
        "datetime",
        "exception_from_payload",
    }
)
# Members the generated exception binds for itself. A payload field taking one of these would be
# assigned over it in __init__, so the catalogue has to rename. Names starting with an underscore
# are refused outright, which covers __init__ and every other dunder the class relies on.
RESERVED_MEMBER_NAMES = frozenset(
    {
        "CODE",
        "DATA_MODEL",
        "code",
        "errors",
        "extensions",
        "from_payload",
        "http_status",
        "message",
        "model_config",
        "query",
        "self",
        "variables",
    }
)
SCALAR_SCHEMA_TYPES = {"integer": "int", "number": "float", "boolean": "bool", "null": "None"}


class ErrorCatalogueGenerationError(Exception):
    """Raised when the catalogue declares something the generator will not guess at."""


class BindingsState(Enum):
    """What the submodule's committed bindings look like next to a fresh render."""

    UP_TO_DATE = "up_to_date"
    NOT_COMMITTED = "not_committed"
    STALE = "stale"


def classify_bindings_state(*, tracked_at_head: bool, working_tree_differs: bool) -> BindingsState:
    """Decide which of the three states the generated artefact is in.

    An artefact absent from HEAD and one committed but since regenerated need different fixes, and a
    check that only diffs cannot tell them apart: a diff reports nothing for a file Git is not
    tracking, so the first state would read as clean.
    """
    if not tracked_at_head:
        return BindingsState.NOT_COMMITTED
    return BindingsState.STALE if working_tree_differs else BindingsState.UP_TO_DATE


def derive_exception_name(code: str) -> str:
    name = "".join(part.capitalize() for part in code.split("_"))
    return name if name.endswith("Error") else f"{name}Error"


def python_type(schema: object, code: str) -> str:
    """Map one JSON Schema fragment onto the Python type that represents the same value.

    Raises:
        _unsupported_fragment_error: when the fragment is outside the supported vocabulary.

    """
    if not isinstance(schema, dict):
        raise _unsupported_fragment_error(code, schema)

    if "anyOf" in schema:
        branches = schema["anyOf"]
        if not isinstance(branches, list) or not branches:
            raise _unsupported_fragment_error(code, schema)
        # Two branches can collapse to the same Python type; keep the first and drop the repeat.
        return " | ".join(dict.fromkeys(python_type(branch, code) for branch in branches))

    kind = schema.get("type")
    if kind == "string":
        return "datetime" if schema.get("format") == "date-time" else "str"
    if kind == "array":
        items = schema.get("items")
        if not isinstance(items, dict):
            raise _unsupported_fragment_error(code, schema)
        return f"list[{python_type(items, code)}]"
    if isinstance(kind, str) and kind in SCALAR_SCHEMA_TYPES:
        return SCALAR_SCHEMA_TYPES[kind]

    raise _unsupported_fragment_error(code, schema)


def _unsupported_fragment_error(code: str, schema: object) -> ErrorCatalogueGenerationError:
    return ErrorCatalogueGenerationError(
        f'Catalogue code "{code}" uses a JSON Schema construct the generator does not support: '
        f"{json.dumps(schema, sort_keys=True, default=repr)}. Extend the mapping in "
        f"infrahub/errors/sdk_bindings.py rather than letting the bindings guess."
    )


def _python_default(value: object, code: str, field: str) -> str:
    if value is None or isinstance(value, (bool, int, float, str)):
        return repr(value)
    raise ErrorCatalogueGenerationError(
        f'Catalogue code "{code}" declares a default for "{field}" the generator cannot render: '
        f"{json.dumps(value, sort_keys=True, default=repr)}."
    )


def payload_fields(data_schema: dict[str, Any], code: str) -> list[dict[str, Any]]:
    """The payload's fields, required ones first so they can be positional parameters.

    Raises:
        ErrorCatalogueGenerationError: when the payload schema is not shaped as the catalogue declares.

    """
    properties = data_schema.get("properties", {})
    required = data_schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise ErrorCatalogueGenerationError(
            f'Catalogue code "{code}" must declare `data_schema.properties` as an object and '
            f"`data_schema.required` as a list."
        )

    absent = [name for name in required if name not in properties]
    if absent:
        raise ErrorCatalogueGenerationError(
            f'Catalogue code "{code}" marks {absent} required, but declares no such property. '
            f"The generated model would drop the field and accept a payload without it."
        )

    reserved = [name for name in properties if name in RESERVED_MEMBER_NAMES or name.startswith("_")]
    if reserved:
        raise ErrorCatalogueGenerationError(
            f'Catalogue code "{code}" declares payload field(s) {reserved}, which the generated '
            f"exception already binds. Rename the field in the catalogue."
        )

    invalid = [name for name in properties if not _is_plain_identifier(name)]
    if invalid:
        raise ErrorCatalogueGenerationError(
            f'Catalogue code "{code}" declares payload field(s) {invalid} that are not usable as '
            f"Python parameter names."
        )

    fields: list[dict[str, Any]] = [
        {"name": name, "type": python_type(properties[name], code), "default": None}
        for name in properties
        if name in required
    ]

    for name, schema in properties.items():
        if name in required:
            continue
        annotation = python_type(schema, code)
        declared_default = schema.get("default")
        # A field that is merely not required is not thereby nullable: only widen where the schema
        # has no default of its own to fall back on.
        if "None" not in annotation.split(" | ") and declared_default is None:
            annotation = f"{annotation} | None"
        fields.append({"name": name, "type": annotation, "default": _python_default(declared_default, code, name)})

    return fields


def _is_plain_identifier(name: str) -> bool:
    return name.isidentifier() and not keyword.iskeyword(name)


def scan_sdk_exceptions(path: Path) -> tuple[dict[str, str], set[str]]:
    """The codes the SDK's hand-written module adopts, and every name it binds at module level.

    Parsed rather than imported, so the generator needs no installed SDK and a `CODE` a class only
    inherits stays invisible.

    Raises:
        ErrorCatalogueGenerationError: when the module cannot be read, or two classes declare the same code.

    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ErrorCatalogueGenerationError(
            f"Cannot read {SDK_EXCEPTIONS_BASE}: {exc}. Run `git submodule update --init python_sdk` and try again."
        ) from exc
    try:
        module = ast.parse(source)
    except SyntaxError as exc:
        raise ErrorCatalogueGenerationError(f"{SDK_EXCEPTIONS_BASE} does not parse: {exc}.") from exc

    adopted: dict[str, str] = {}
    defined: set[str] = set()

    # Only module level: a class nested in a function or a TYPE_CHECKING block binds no name the
    # generated module could collide with, and its `CODE` adopts nothing.
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defined.add(node.target.id)
        elif isinstance(node, ast.Assign):
            defined.update(target.id for target in node.targets if isinstance(target, ast.Name))
        if not isinstance(node, ast.ClassDef):
            continue
        defined.add(node.name)

        for statement in node.body:
            if isinstance(statement, ast.AnnAssign):
                targets: list[ast.expr] = [statement.target]
            elif isinstance(statement, ast.Assign):
                targets = list(statement.targets)
            else:
                continue
            if not any(isinstance(target, ast.Name) and target.id == "CODE" for target in targets):
                continue
            # A `CODE` assigned anything but a string constant is how a subclass disclaims the code
            # it would otherwise inherit, so it is not an adoption.
            value = statement.value
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            if value.value in adopted:
                raise ErrorCatalogueGenerationError(
                    f'{SDK_EXCEPTIONS_BASE} declares CODE = "{value.value}" on both '
                    f"{adopted[value.value]} and {node.name}. A code can be adopted by one class."
                )
            adopted[value.value] = node.name

    return adopted, defined


def load_catalogue(path: Path) -> dict[str, Any]:
    """Read and validate the catalogue artefact.

    Raises:
        ErrorCatalogueGenerationError: when the file is unreadable, is not JSON, or is misshapen.

    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ErrorCatalogueGenerationError(
            f"Cannot read {CATALOGUE_SOURCE}: {exc}. Run `uv run invoke backend.export-error-catalogue` to write it."
        ) from exc
    try:
        catalogue = json.loads(source)
    except json.JSONDecodeError as exc:
        raise ErrorCatalogueGenerationError(f"{CATALOGUE_SOURCE} is not valid JSON: {exc}.") from exc

    validate_catalogue(catalogue)
    return catalogue


def validate_catalogue(catalogue: object) -> None:
    """Refuse a catalogue the generator cannot read.

    Raises:
        ErrorCatalogueGenerationError: when the root, the version, or `codes` is missing or misshapen.

    """
    if not isinstance(catalogue, dict):
        raise ErrorCatalogueGenerationError(f"{CATALOGUE_SOURCE} root must be an object.")

    version = catalogue.get("infrahub_catalogue_version")
    if not isinstance(version, (str, int)) or not str(version).strip():
        raise ErrorCatalogueGenerationError(
            f"{CATALOGUE_SOURCE} must declare `infrahub_catalogue_version`, which the generated "
            f"header records (got {version!r})."
        )

    codes = catalogue.get("codes")
    if not isinstance(codes, dict):
        raise ErrorCatalogueGenerationError(f"{CATALOGUE_SOURCE} must contain a `codes` object.")
    if not codes:
        raise ErrorCatalogueGenerationError(f"{CATALOGUE_SOURCE} `codes` is empty.")


def _validated_entry(code: str, entry: object) -> tuple[int, dict[str, Any], str]:
    if not isinstance(entry, dict):
        raise ErrorCatalogueGenerationError(f'Catalogue code "{code}" must be an object.')

    http_status = entry.get("http_status")
    # `bool` is an `int` in Python and a status is not a flag.
    if not isinstance(http_status, int) or isinstance(http_status, bool):
        raise ErrorCatalogueGenerationError(
            f'Catalogue code "{code}" must declare an integer `http_status` (got {http_status!r}).'
        )

    data_schema = entry.get("data_schema")
    if not isinstance(data_schema, dict):
        raise ErrorCatalogueGenerationError(f'Catalogue code "{code}" must declare a `data_schema` object.')

    title = data_schema.get("title")
    if not isinstance(title, str) or not title:
        raise ErrorCatalogueGenerationError(
            f'Catalogue code "{code}" must declare a non-empty `data_schema.title`, which names its payload model.'
        )

    return http_status, data_schema, title


def build_bindings_context(catalogue: dict[str, Any], adopted: dict[str, str], defined: set[str]) -> dict[str, Any]:
    """Everything the template needs, derived from the catalogue and the SDK's own module.

    Raises:
        ErrorCatalogueGenerationError: when a code would emit a shadowed, duplicated or unusable name.

    """
    codes: dict[str, Any] = catalogue["codes"]

    payload_models: list[dict[str, Any]] = []
    exception_classes: list[dict[str, Any]] = []
    code_to_exception: list[tuple[str, str]] = []
    code_to_data_model: list[tuple[str, str]] = []
    builders: list[dict[str, str]] = []
    adopted_imports: set[str] = set()
    emitted_names: dict[str, str] = {}

    # Sorted so that reordering the catalogue's JSON does not churn the diff.
    for code in sorted(codes):
        entry = codes[code]
        http_status, data_schema, model_name = _validated_entry(code, entry)
        fields = payload_fields(data_schema, code)

        _claim_name(emitted_names, model_name, code, defined)
        payload_models.append({"name": model_name, "code": code, "fields": fields})
        code_to_data_model.append((code, model_name))

        # The transport rule outranks adoption: these codes must miss the lookup so the exception
        # follows the HTTP response the SDK saw. Adopting one contradicts that, so say which.
        if http_status in TRANSPORT_OWNED_STATUSES:
            if code in adopted:
                raise ErrorCatalogueGenerationError(
                    f'{SDK_EXCEPTIONS_BASE} adopts "{code}" on {adopted[code]}, but the catalogue gives '
                    f"it HTTP {http_status}, which the SDK resolves from the response instead. Drop the "
                    f"CODE declaration, or change the code's status."
                )
            continue
        if code in adopted:
            adopted_imports.add(adopted[code])
            code_to_exception.append((code, adopted[code]))
            builders.append(_builder(emitted_names, code, adopted[code], model_name))
            continue

        name = derive_exception_name(code)
        # Pre-empts the same check inside _claim_name, which cannot offer the adoption hint.
        if name in defined:
            raise ErrorCatalogueGenerationError(
                f'Catalogue code "{code}" derives the class name "{name}", which {SDK_EXCEPTIONS_BASE} '
                f"already defines without declaring that code. The generated class would silently "
                f'shadow it. Declare CODE = "{code}" on that class to adopt the code, or rename the '
                f"catalogue code."
            )
        _claim_name(emitted_names, name, code, defined)

        description = " ".join(str(entry.get("description") or "").split())
        if '"""' in description or "\\" in description:
            raise ErrorCatalogueGenerationError(
                f'Catalogue code "{code}" has a description carrying a quote or backslash sequence that '
                f"would break the generated docstring."
            )
        exception_classes.append(
            {
                "name": name,
                "parent": "GraphQLError",
                "code": code,
                "http_status": http_status,
                "model": model_name,
                "summary": f"Raised when the server reports {code}.",
                "description": textwrap.fill(description, width=104, subsequent_indent="    "),
                "stability": entry.get("stability") or "unspecified",
                "fields": fields,
            }
        )
        code_to_exception.append((code, name))
        builders.append(_builder(emitted_names, code, name, model_name))

    public = [*emitted_names, "CODE_TO_DATA_MODEL", "CODE_TO_EXCEPTION", "exception_from_payload"]
    return {
        "catalogue_version": catalogue.get("infrahub_catalogue_version"),
        "base_imports": sorted({"GraphQLError", *adopted_imports}),
        "exported_names": sorted((n for n in public if not n.startswith("_")), key=dunder_all_sort_key),
        "payload_models": payload_models,
        "exception_classes": exception_classes,
        "code_to_exception": code_to_exception,
        "code_to_data_model": code_to_data_model,
        "builders": builders,
        "needs_datetime": any("datetime" in field["type"] for model in payload_models for field in model["fields"]),
    }


def dunder_all_sort_key(name: str) -> tuple[int, list[tuple[int, str]], str]:
    """Reproduce the order ruff enforces on `__all__`, so the render needs no fixing afterwards.

    Constants first, then classes, then everything else; within a group, runs of digits compare as
    numbers so `Code2Data` precedes `Code10Data`, and equal numbers fall back to the raw spelling.
    """
    if name.isupper():
        group = 0
    elif name[:1].isupper():
        group = 1
    else:
        group = 2

    chunks = [(int(part), "") if part.isdigit() else (-1, part) for part in re.split(r"(\d+)", name) if part]
    return group, chunks, name


def _builder(emitted: dict[str, str], code: str, exception: str, model: str) -> dict[str, str]:
    """One code's builder: named rather than a lambda, so a traceback names the code that failed."""
    name = f"_build_{code.lower()}"
    _claim_name(emitted, name, code, set())
    return {"name": name, "code": code, "exception": exception, "model": model}


def _claim_name(emitted: dict[str, str], name: str, code: str, defined: set[str]) -> None:
    """Reserve one top-level name in the generated module, refusing any name already spoken for.

    Raises:
        ErrorCatalogueGenerationError: when the name is unusable, or another code or the SDK owns it.

    """
    if not _is_plain_identifier(name):
        raise ErrorCatalogueGenerationError(
            f'Catalogue code "{code}" emits the name "{name}", which is not a Python identifier.'
        )
    if name in GENERATED_MODULE_NAMES:
        raise ErrorCatalogueGenerationError(
            f'Catalogue code "{code}" emits the name "{name}", which the generated module already '
            f"binds. Rename the code or its `data_schema.title`."
        )
    if name in emitted:
        raise ErrorCatalogueGenerationError(
            f'Catalogue codes "{emitted[name]}" and "{code}" both emit the name "{name}".'
        )
    if name in defined:
        raise ErrorCatalogueGenerationError(
            f'Catalogue code "{code}" emits the name "{name}", which {SDK_EXCEPTIONS_BASE} already defines.'
        )
    emitted[name] = code


def render_bindings(catalogue: dict[str, Any], adopted: dict[str, str], defined: set[str], template_dir: Path) -> str:
    """Render the bindings module, refusing to return anything that does not parse as Python.

    Raises:
        ErrorCatalogueGenerationError: when the render does not parse.

    """
    from jinja2 import Environment, FileSystemLoader, StrictUndefined  # noqa: PLC0415

    # autoescape stays off: the output is Python source, not markup, and HTML-escaping it would
    # corrupt every quote and operator in the rendered module.
    environment = Environment(  # noqa: S701
        loader=FileSystemLoader(str(template_dir)), undefined=StrictUndefined, keep_trailing_newline=True
    )
    rendered = environment.get_template(TEMPLATE_NAME).render(**build_bindings_context(catalogue, adopted, defined))

    # Parsing here keeps a broken render out of the submodule, where it would otherwise surface as a
    # parse error from ruff with the bad file already written.
    try:
        ast.parse(rendered)
    except SyntaxError as exc:
        raise ErrorCatalogueGenerationError(
            f"The rendered bindings do not parse ({exc.msg} at line {exc.lineno}). "
            f"Nothing was written; fix backend/templates/{TEMPLATE_NAME}."
        ) from exc

    return rendered
