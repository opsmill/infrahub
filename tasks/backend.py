from pathlib import Path
from typing import Any

from invoke import Context, task
from invoke.runners import Result

from .shared import (
    INFRAHUB_DATABASE,
    NBR_WORKERS,
    PYTHON_PRIMITIVE_MAP,
    execute_command,
)
from .utils import ESCAPED_REPO_PATH, REPO_BASE

MAIN_DIRECTORY = "backend"
NAMESPACE = "BACKEND"


# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------


def _format_ruff(context: Context) -> None:
    """Run ruff to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with ruff")
    exec_cmd = f"uv run ruff format {MAIN_DIRECTORY} --config {REPO_BASE}/pyproject.toml && "
    exec_cmd += f"uv run ruff check --fix {MAIN_DIRECTORY} --config {REPO_BASE}/pyproject.toml"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task(name="format")
def format_all(context: Context) -> None:
    """This will run all formatter."""

    _format_ruff(context)

    print(f" - [{NAMESPACE}] All formatters have been executed!")


# ----------------------------------------------------------------------------
# Testing tasks
# ----------------------------------------------------------------------------
@task
def ruff(context: Context) -> None:
    """Run ruff to check that Python files adherence to ruff standards."""

    print(f" - [{NAMESPACE}] Check code with ruff")
    exec_cmd = f"uv run ruff check --diff {MAIN_DIRECTORY} --config {REPO_BASE}/pyproject.toml"

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)

    exec_cmd = f"uv run ruff format --check --diff {MAIN_DIRECTORY} --config {REPO_BASE}/pyproject.toml"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def ty(context: Context) -> None:
    """Run ty type checker against project files."""

    print(f" - [{NAMESPACE}] Check code with ty")
    exec_cmd = "uv run ty check ."

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def mypy(context: Context) -> None:
    """This will run mypy for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with mypy")
    exec_cmd = f"uv run mypy --show-error-codes {MAIN_DIRECTORY}"

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def lint(context: Context) -> None:
    """This will run all linters."""
    ruff(context)
    ty(context)
    mypy(context)

    print(f" - [{NAMESPACE}] All tests have passed!")


@task(optional=["database"])
def test_unit(context: Context, database: str = INFRAHUB_DATABASE) -> Result | None:
    with context.cd(ESCAPED_REPO_PATH):
        exec_cmd = f"uv run pytest -n {NBR_WORKERS} -v --cov=infrahub {MAIN_DIRECTORY}/tests/unit"
        if database == "neo4j":
            exec_cmd += " --neo4j"
        print(f"{exec_cmd}")
        return execute_command(context=context, command=f"{exec_cmd}")


@task(optional=["database"])
def test_core(context: Context, database: str = INFRAHUB_DATABASE) -> Result | None:
    with context.cd(ESCAPED_REPO_PATH):
        exec_cmd = f"uv run pytest -n {NBR_WORKERS} -v --cov=infrahub {MAIN_DIRECTORY}/tests/unit/core"
        if database == "neo4j":
            exec_cmd += " --neo4j"
        print(f"{exec_cmd}")
        return execute_command(context=context, command=f"{exec_cmd}")


@task(optional=["database"])
def test_integration(context: Context, database: str = INFRAHUB_DATABASE) -> Result | None:
    with context.cd(ESCAPED_REPO_PATH):
        exec_cmd = f"uv run pytest -n {NBR_WORKERS} -v --cov=infrahub {MAIN_DIRECTORY}/tests/integration"
        if database == "neo4j":
            exec_cmd += " --neo4j"
        print(f"{exec_cmd=}")
        return execute_command(context=context, command=f"{exec_cmd}")


@task(optional=["database"])
def test_functional(context: Context, database: str = INFRAHUB_DATABASE) -> Result | None:
    with context.cd(ESCAPED_REPO_PATH):
        exec_cmd = f"uv run pytest -n {NBR_WORKERS} -v --cov=infrahub {MAIN_DIRECTORY}/tests/functional"
        if database == "neo4j":
            exec_cmd += " --neo4j"
        print(f"{exec_cmd=}")
        return execute_command(context=context, command=f"{exec_cmd}")


@task(optional=["schema", "stager", "amount", "test", "attrs", "rels", "changes"])
def test_scale(
    context: Context,
    schema: Path = f"{ESCAPED_REPO_PATH}/backend/tests/scale/schema.yml",
    stager: str | None = None,
    amount: int | None = None,
    test: str | None = None,
    attrs: int | None = None,
    rels: int | None = None,
    changes: int | None = None,
) -> Result | None:
    args = []
    if stager:
        args.extend(["--stager", stager])

    if amount:
        args.extend(["--amount", amount])

    if test:
        args.extend(["--test", test])

    if schema:
        args.extend(["--schema", schema])

    if attrs:
        args.extend(["--attrs", attrs])

    if rels:
        args.extend(["--rels", rels])

    if changes:
        args.extend(["--changes", changes])

    with context.cd(ESCAPED_REPO_PATH):
        base_cmd = ["python", "backend/tests/scale/main.py"]
        cmd = " ".join(base_cmd + args)
        print(f"{cmd}")
        return execute_command(context=context, command=cmd)


@task(default=True)
def format_and_lint(context: Context) -> None:
    format_all(context)
    lint(context)


# ----------------------------------------------------------------------------
# Generate tasks
# ----------------------------------------------------------------------------


@task
def generate(context: Context) -> None:
    """Generate internal backend models."""
    _generate_schemas(context=context)
    _generate_protocols(context=context)


@task
def validate_generated(context: Context, docker: bool = False) -> None:  # noqa: ARG001
    """Validate that the generated documentation is committed to Git."""

    _generate_schemas(context=context)
    exec_cmd = "git diff --exit-code backend/infrahub/core/schema/generated"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)

    _generate_protocols(context=context)
    exec_cmd = "git diff --exit-code backend/infrahub/core/protocols.py backend/tests/protocols.py"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


def _generate_schemas(context: Context) -> None:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from infrahub.core.schema.definitions.internal import (
        attribute_schema,
        base_node_schema,
        generic_schema,
        node_schema,
        relationship_schema,
    )

    env = Environment(loader=FileSystemLoader(f"{ESCAPED_REPO_PATH}/backend/templates"), undefined=StrictUndefined)
    generated = f"{ESCAPED_REPO_PATH}/backend/infrahub/core/schema/generated"
    template = env.get_template("generate_schema.j2")

    attributes_rendered = template.render(schema="AttributeSchema", node=attribute_schema, parent="HashableModel")
    attribute_schema_output = f"{generated}/attribute_schema.py"
    Path(attribute_schema_output).write_text(attributes_rendered, encoding="utf-8")

    base_node_rendered = template.render(schema="BaseNodeSchema", node=base_node_schema, parent="HashableModel")
    base_node_schema_output = f"{generated}/base_node_schema.py"
    Path(base_node_schema_output).write_text(base_node_rendered, encoding="utf-8")

    generic_schema_stripped = generic_schema.without_duplicates(base_node_schema)
    generic_rendered = template.render(schema="GenericSchema", node=generic_schema_stripped, parent="BaseNodeSchema")
    generic_schema_output = f"{generated}/genericnode_schema.py"
    Path(generic_schema_output).write_text(generic_rendered, encoding="utf-8")

    node_schema_stripped = node_schema.without_duplicates(base_node_schema)
    node_rendered = template.render(schema="NodeSchema", node=node_schema_stripped, parent="BaseNodeSchema")
    node_schema_output = f"{generated}/node_schema.py"
    Path(node_schema_output).write_text(node_rendered, encoding="utf-8")

    relationship_rendered = template.render(
        schema="RelationshipSchema", node=relationship_schema, parent="HashableModel"
    )
    relationship_schema_output = f"{generated}/relationship_schema.py"
    Path(relationship_schema_output).write_text(relationship_rendered, encoding="utf-8")

    execute_command(context=context, command=f"ruff format {generated}")
    execute_command(context=context, command=f"ruff check --fix {generated}")


def _jinja2_filter_inheritance(value: dict[str, Any], sync: bool = False) -> str:
    inherit_from: list[str] = value.get("inherit_from", [])

    suffix = "Sync" if sync else ""

    if not inherit_from:
        return f"CoreNode{suffix}"
    return ", ".join([f"{item}{suffix}" for item in inherit_from])


def _jinja2_filter_render_attribute(value: dict[str, Any], use_python_primitive: bool = False) -> str:
    from infrahub.types import ATTRIBUTE_TYPES

    attr_name: str = value["name"]
    attr_kind: str = value["kind"]
    optional: bool = value.get("optional", False)

    if "enum" in value and not use_python_primitive:
        return f"{attr_name}: Enum"

    if use_python_primitive:
        value = PYTHON_PRIMITIVE_MAP[attr_kind.lower()]
        if optional:
            value = f"Optional[{value}]"
        return f"{attr_name}: {value}"

    value = ATTRIBUTE_TYPES[attr_kind].infrahub
    if optional:
        value = f"{value}Optional"
    return f"{attr_name}: {value}"


def _sort_and_filter_models(
    models: list[dict[str, Any]], filters: list[tuple[str, str]] | None = None
) -> list[dict[str, Any]]:
    if filters is None:
        filters = [("Core", "Node")]

    filtered: list[dict[str, Any]] = []

    for model in models:
        if (model["namespace"], model["name"]) in filters:
            continue
        filtered.append(model)

    return sorted(filtered, key=lambda k: (k["namespace"].lower(), k["name"].lower()))


def _generate_protocols(context: Context) -> None:
    import sys

    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from infrahub.core.schema.definitions.core import core_models

    # We need to insert this folder in the search order to ensure
    # that it appears before the python_sdk folder since that folder also has
    # a 'tests' module and the sys.path seems to be random between runs.
    sys.path.insert(0, f"{ESCAPED_REPO_PATH}/backend")
    from tests.helpers.schema import test_models

    env = Environment(loader=FileSystemLoader(f"{ESCAPED_REPO_PATH}/backend/templates"), undefined=StrictUndefined)
    env.filters["inheritance"] = _jinja2_filter_inheritance
    env.filters["render_attribute"] = _jinja2_filter_render_attribute

    # Export protocols for backend code use
    generated = f"{ESCAPED_REPO_PATH}/backend/infrahub/core"
    template = env.get_template("generate_protocols.j2")

    protocols_rendered = template.render(
        generics=_sort_and_filter_models(core_models["generics"]), models=_sort_and_filter_models(core_models["nodes"])
    )
    protocols_output = f"{generated}/protocols.py"
    Path(protocols_output).write_text(protocols_rendered, encoding="utf-8")

    execute_command(context=context, command=f"ruff format {protocols_output}")
    execute_command(context=context, command=f"ruff check --fix {protocols_output}")

    # Export test protocols for backend code use
    generated = f"{ESCAPED_REPO_PATH}/backend/tests/"

    test_models["nodes"].extend(core_models["nodes"])
    test_models["generics"].extend(core_models["generics"])
    protocols_rendered = template.render(
        generics=_sort_and_filter_models(test_models["generics"]), models=_sort_and_filter_models(test_models["nodes"])
    )
    protocols_output = f"{generated}/protocols.py"
    Path(protocols_output).write_text(protocols_rendered, encoding="utf-8")

    execute_command(context=context, command=f"ruff format {protocols_output}")
    execute_command(context=context, command=f"ruff check --fix {protocols_output}")

    # Export protocols for Python SDK code use
    generated = f"{ESCAPED_REPO_PATH}/python_sdk/infrahub_sdk"
    template = env.get_template("generate_protocols_sdk.j2")

    protocols_rendered = template.render(
        generics=_sort_and_filter_models(core_models["generics"]), models=_sort_and_filter_models(core_models["nodes"])
    )
    protocols_output = f"{generated}/protocols.py"
    Path(protocols_output).write_text(protocols_rendered, encoding="utf-8")

    execute_command(context=context, command=f"ruff format {protocols_output}")
    execute_command(context=context, command=f"ruff check --fix {protocols_output}")
