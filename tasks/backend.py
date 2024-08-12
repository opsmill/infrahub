from pathlib import Path
from typing import Any, Optional

from invoke import Context, task

from .shared import (
    BUILD_NAME,
    INFRAHUB_DATABASE,
    NBR_WORKERS,
    PYTHON_PRIMITIVE_MAP,
    build_test_compose_files_cmd,
    build_test_envs,
    build_test_scale_compose_files_cmd,
    execute_command,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH, REPO_BASE

MAIN_DIRECTORY = "backend"
NAMESPACE = "BACKEND"


# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------


def _format_ruff(context: Context):
    """Run ruff to format all Python files."""

    print(f" - [{NAMESPACE}] Format code with ruff")
    exec_cmd = f"ruff format {MAIN_DIRECTORY} --config {REPO_BASE}/pyproject.toml && "
    exec_cmd += f"ruff check --fix {MAIN_DIRECTORY} --config {REPO_BASE}/pyproject.toml"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task(name="format")
def format_all(context: Context):
    """This will run all formatter."""

    _format_ruff(context)

    print(f" - [{NAMESPACE}] All formatters have been executed!")


# ----------------------------------------------------------------------------
# Testing tasks
# ----------------------------------------------------------------------------
@task
def ruff(context: Context, docker: bool = False):
    """Run ruff to check that Python files adherence to black standards."""

    print(f" - [{NAMESPACE}] Check code with ruff")
    exec_cmd = f"ruff check --diff {MAIN_DIRECTORY} --config {REPO_BASE}/pyproject.toml"

    if docker:
        compose_files_cmd = build_test_compose_files_cmd(database=False)
        exec_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run  {build_test_envs()} infrahub-test {exec_cmd}"
        print(exec_cmd)

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def mypy(context: Context, docker: bool = False):
    """This will run mypy for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with mypy")
    exec_cmd = f"mypy --show-error-codes {MAIN_DIRECTORY}"

    if docker:
        compose_files_cmd = build_test_compose_files_cmd(database=False)
        exec_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run {build_test_envs()} infrahub-test {exec_cmd}"
        print(exec_cmd)

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def pylint(context: Context, docker: bool = False):
    """This will run pylint for the specified name and Python version."""

    print(f" - [{NAMESPACE}] Check code with pylint")
    exec_cmd = f"pylint --ignore-paths {MAIN_DIRECTORY}/tests {MAIN_DIRECTORY}"

    if docker:
        compose_files_cmd = build_test_compose_files_cmd(database=False)
        exec_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run {build_test_envs()} infrahub-test {exec_cmd}"
        print(exec_cmd)

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def lint(context: Context, docker: bool = False):
    """This will run all linter."""
    ruff(context, docker=docker)
    mypy(context, docker=docker)
    pylint(context, docker=docker)

    print(f" - [{NAMESPACE}] All tests have passed!")


@task(optional=["database"])
def test_unit(context: Context, database: str = INFRAHUB_DATABASE):
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_test_compose_files_cmd(database=database)
        base_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run {build_test_envs()} infrahub-test"
        exec_cmd = f"pytest -n {NBR_WORKERS} -v --cov=infrahub {MAIN_DIRECTORY}/tests/unit"
        if database == "neo4j":
            exec_cmd += " --neo4j"
        print(f"{base_cmd} {exec_cmd}")
        return execute_command(context=context, command=f"{base_cmd} {exec_cmd}")


@task(optional=["database"])
def test_core(context: Context, database: str = INFRAHUB_DATABASE):
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_test_compose_files_cmd(database=database)
        base_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run {build_test_envs()} infrahub-test"
        exec_cmd = f"pytest -n {NBR_WORKERS} -v --cov=infrahub {MAIN_DIRECTORY}/tests/unit/core"
        if database == "neo4j":
            exec_cmd += " --neo4j"
        print(f"{base_cmd} {exec_cmd}")
        return execute_command(context=context, command=f"{base_cmd} {exec_cmd}")


@task(optional=["database"])
def test_integration(context: Context, database: str = INFRAHUB_DATABASE):
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_test_compose_files_cmd(database=database)
        base_cmd = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} run {build_test_envs()} infrahub-test"
        exec_cmd = f"pytest -n {NBR_WORKERS} -v --cov=infrahub {MAIN_DIRECTORY}/tests/integration"
        if database == "neo4j":
            exec_cmd += " --neo4j"
        print(f"{base_cmd} {exec_cmd}")
        return execute_command(context=context, command=f"{base_cmd} {exec_cmd}")


@task
def test_scale_env_start(context: Context, database: str = INFRAHUB_DATABASE, gunicorn_workers: int = 4):
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_test_scale_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} GUNICORN_WORKERS={gunicorn_workers} docker compose {compose_files_cmd} -p {BUILD_NAME} up -d"
        return execute_command(context=context, command=command)


@task
def test_scale_env_destroy(context: Context, database: str = INFRAHUB_DATABASE):
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_test_scale_compose_files_cmd(database=database)
        command = f"{get_env_vars(context)} docker compose {compose_files_cmd} -p {BUILD_NAME} down --remove-orphans --volumes"
        return execute_command(context=context, command=command)


@task(optional=["schema", "stager", "amount", "test", "attrs", "rels", "changes"])
def test_scale(
    context: Context,
    schema: Path = f"{ESCAPED_REPO_PATH}/backend/tests/scale/schema.yml",
    stager: str = None,
    amount: int = None,
    test: str = None,
    attrs: int = None,
    rels: int = None,
    changes: int = None,
):
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
def format_and_lint(context: Context):
    format_all(context)
    lint(context)


# ----------------------------------------------------------------------------
# Generate tasks
# ----------------------------------------------------------------------------


@task
def generate(context: Context):
    """Generate internal backend models."""
    _generate_schemas(context=context)
    _generate_protocols(context=context)


@task
def validate_generated(context: Context, docker: bool = False):
    """Validate that the generated documentation is committed to Git."""

    _generate_schemas(context=context)
    exec_cmd = "git diff --exit-code backend/infrahub/core/schema/generated"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)

    _generate_protocols(context=context)
    exec_cmd = "git diff --exit-code backend/infrahub/core/protocols.py"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


def _generate_schemas(context: Context):
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
    models: list[dict[str, Any]], filters: Optional[list[tuple[str, str]]] = None
) -> list[dict[str, Any]]:
    if filters is None:
        filters = [("Core", "Node")]

    filtered: list[dict[str, Any]] = []

    for model in models:
        if (model["namespace"], model["name"]) in filters:
            continue
        filtered.append(model)

    return sorted(filtered, key=lambda k: (k["namespace"].lower(), k["name"].lower()))


def _generate_protocols(context: Context):
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from infrahub.core.schema.definitions.core import core_models

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
