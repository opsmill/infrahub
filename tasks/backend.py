from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from invoke import Context, task
from invoke.runners import Result

if TYPE_CHECKING:
    from jinja2 import Template

    from infrahub.core.constants import Visibility
    from infrahub.core.schema.definitions.internal import SchemaNode

from .shared import (
    INFRAHUB_DATABASE,
    NBR_WORKERS,
    PYTHON_PRIMITIVE_MAP,
    execute_command,
)
from .utils import ESCAPED_REPO_PATH, REPO_BASE

MAIN_DIRECTORY = "backend"
NAMESPACE = "BACKEND"

COMPONENT_TEST_DIRECTORY = f"{MAIN_DIRECTORY}/tests/component"

# Component test shards used by CI to run backend.test-component in parallel jobs.
# Directories listed here are run by their named shard; everything else falls into the
# "other" catch-all shard, which ignores exactly the directories assigned below so new
# test directories are picked up automatically. The partition is verified by
# backend.validate-component-shards. Shard contents are sized from measured durations,
# rebalance when they drift apart.
COMPONENT_TEST_SHARDS: dict[str, list[str]] = {
    "graphql": ["graphql"],
    "core-diff": ["core/diff", "core/migrations", "core/changelog"],
    "core-schema": [
        "core/schema",
        "core/schema_manager",
        "core/constraint_validators",
        "core/ipam",
        "core/resource_manager",
        "core/convert_object_type",
        "core/profiles",
        "core/node",
        "core/hierarchy",
        "core/graph",
    ],
}
COMPONENT_TEST_CATCHALL_SHARD = "other"


def _component_shard_targets(shard: str) -> str:
    """Build the pytest path arguments for a component test shard.

    The catch-all shard must be expressed with --ignore flags only: pytest drops an
    explicit child path when an ancestor path is also passed positionally.

    Raises:
        ValueError: If the shard name is unknown.

    """
    if shard == COMPONENT_TEST_CATCHALL_SHARD:
        ignored = [path for paths in COMPONENT_TEST_SHARDS.values() for path in paths]
        ignore_args = " ".join(f"--ignore={COMPONENT_TEST_DIRECTORY}/{path}" for path in ignored)
        return f"{COMPONENT_TEST_DIRECTORY} {ignore_args}"
    if shard not in COMPONENT_TEST_SHARDS:
        valid_shards = ", ".join([*COMPONENT_TEST_SHARDS, COMPONENT_TEST_CATCHALL_SHARD])
        raise ValueError(f"Unknown component test shard '{shard}', expected one of: {valid_shards}")
    return " ".join(f"{COMPONENT_TEST_DIRECTORY}/{path}" for path in COMPONENT_TEST_SHARDS[shard])


# ----------------------------------------------------------------------------
# Formatting tasks
# ----------------------------------------------------------------------------


def _format_ruff(context: Context) -> None:
    """Run ruff to format all Python files."""
    print(f" - [{NAMESPACE}] Format code with ruff")
    exec_cmd = f"uv run ruff format {MAIN_DIRECTORY} &&"
    exec_cmd += f"uv run ruff check --fix {MAIN_DIRECTORY}"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task(name="format")
def format_all(context: Context) -> None:
    """Format all backend Python files with ruff."""
    _format_ruff(context)

    print(f" - [{NAMESPACE}] All formatters have been executed!")


# ----------------------------------------------------------------------------
# Testing tasks
# ----------------------------------------------------------------------------
@task
def ruff(context: Context) -> None:
    """Run ruff linter against backend Python files."""
    print(f" - [{NAMESPACE}] Check code with ruff")
    exec_cmd = f"uv run ruff check --diff {MAIN_DIRECTORY}"

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)

    exec_cmd = f"uv run ruff format --check --diff {MAIN_DIRECTORY}"
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
    """Run mypy type checking against backend Python files."""
    print(f" - [{NAMESPACE}] Check code with mypy")
    exec_cmd = f"uv run mypy --show-error-codes {MAIN_DIRECTORY}"

    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task
def lint(context: Context) -> None:
    """Run all backend linters (ruff, ty, mypy)."""
    ruff(context)
    ty(context)
    mypy(context)

    print(f" - [{NAMESPACE}] All tests have passed!")


@task(optional=["database"])
def test_component(context: Context, database: str = INFRAHUB_DATABASE, shard: str | None = None) -> Result | None:
    """Run backend component tests, optionally restricted to a single shard."""
    targets = _component_shard_targets(shard) if shard else f"{MAIN_DIRECTORY}/tests/component"
    with context.cd(ESCAPED_REPO_PATH):
        exec_cmd = f"uv run pytest -n {NBR_WORKERS} -v --cov=infrahub --durations=20 {targets}"
        if database == "neo4j":
            exec_cmd += " --neo4j"
        print(f"{exec_cmd}")
        return execute_command(context=context, command=f"{exec_cmd}")


@task
def validate_component_shards(context: Context) -> None:
    """Verify that the component test shards cover the full component test suite exactly once.

    Raises:
        RuntimeError: If test collection fails or the shards do not partition the full suite.

    """

    def collect(targets: str) -> list[str]:
        result = execute_command(
            context=context,
            command=f"uv run pytest --collect-only -qq -p no:cacheprovider {targets}",
            hide=True,
        )
        if result is None:
            raise RuntimeError(f"Failed to collect tests for: {targets}")
        return [line for line in result.stdout.splitlines() if line.startswith(f"{COMPONENT_TEST_DIRECTORY}/")]

    with context.cd(ESCAPED_REPO_PATH):
        full_suite = sorted(collect(COMPONENT_TEST_DIRECTORY))
        all_shards = [*COMPONENT_TEST_SHARDS, COMPONENT_TEST_CATCHALL_SHARD]
        sharded = sorted(test for shard in all_shards for test in collect(_component_shard_targets(shard)))

    if full_suite != sharded:
        full_set = set(full_suite)
        shard_set = set(sharded)
        missing = sorted(full_set - shard_set)
        duplicated = sorted({test for test in sharded if sharded.count(test) > 1} | (shard_set - full_set))
        msg = f"Component test shards do not match the full suite ({len(sharded)} vs {len(full_suite)} tests)."
        if missing:
            msg += f"\nMissing from all shards ({len(missing)}): " + ", ".join(missing[:10])
        if duplicated:
            msg += f"\nCollected more than once ({len(duplicated)}): " + ", ".join(duplicated[:10])
        raise RuntimeError(msg)

    print(
        f" - [{NAMESPACE}] Component test shards are consistent ({len(full_suite)} tests across {len(all_shards)} shards)"
    )


@task
def test_unit(context: Context) -> Result | None:
    """Run backend unit tests."""
    with context.cd(ESCAPED_REPO_PATH):
        exec_cmd = f"uv run pytest --cov=infrahub {MAIN_DIRECTORY}/tests/unit"
        print(f"{exec_cmd}")
        return execute_command(context=context, command=f"{exec_cmd}")


@task(optional=["database"])
def test_core(context: Context, database: str = INFRAHUB_DATABASE) -> Result | None:
    """Run backend core component tests."""
    with context.cd(ESCAPED_REPO_PATH):
        exec_cmd = f"uv run pytest -n {NBR_WORKERS} -v --cov=infrahub {MAIN_DIRECTORY}/tests/component/core"
        if database == "neo4j":
            exec_cmd += " --neo4j"
        print(f"{exec_cmd}")
        return execute_command(context=context, command=f"{exec_cmd}")


@task(optional=["database"])
def test_integration(context: Context, database: str = INFRAHUB_DATABASE) -> Result | None:
    """Run backend integration tests."""
    with context.cd(ESCAPED_REPO_PATH):
        exec_cmd = f"uv run pytest -n {NBR_WORKERS} -v --cov=infrahub {MAIN_DIRECTORY}/tests/integration"
        if database == "neo4j":
            exec_cmd += " --neo4j"
        print(f"{exec_cmd=}")
        return execute_command(context=context, command=f"{exec_cmd}")


@task(optional=["database"])
def test_functional(context: Context, database: str = INFRAHUB_DATABASE) -> Result | None:
    """Run backend functional tests."""
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
    """Run backend scale/performance tests."""
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
    """Format and lint all backend Python files."""
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


GRAPHQL_QUERY_FILES = [
    "backend/infrahub/generators/graphql_queries/generator_instance_fetch.gql",
    "backend/infrahub/computed_attribute/graphql_queries/transform_fetch.gql",
]


def _generate_custom_graphql_types(context: Context) -> None:
    for gql_file in GRAPHQL_QUERY_FILES:
        execute_command(
            context=context,
            command=f"uv run infrahubctl graphql generate-return-types {gql_file} --schema schema/schema.graphql",
        )
        execute_command(context=context, command=f'uv run ruff check --fix "{Path(gql_file).parent}"')
        execute_command(context=context, command=f'uv run ruff format "{Path(gql_file).parent}"')


@task
def generate_custom_graphql_types(context: Context) -> None:
    """Generate Pydantic models from .gql query files using infrahubctl."""
    _generate_custom_graphql_types(context=context)


@task
def validate_generated(context: Context, docker: bool = False) -> None:  # noqa: ARG001
    """Validate that generated schemas and protocols are committed to Git."""
    _generate_schemas(context=context)
    exec_cmd = "git diff --exit-code backend/infrahub/core/schema/generated"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)

    # The user-facing schema models live in the Python SDK submodule but are generated here from
    # the same internal definitions. `git diff` from the superproject only tracks the submodule
    # pointer, so the diff must run inside the submodule to see the generated files themselves.
    exec_cmd = "git -C python_sdk diff --exit-code infrahub_sdk/schema/generated"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)

    _generate_protocols(context=context)
    exec_cmd = "git diff --exit-code backend/infrahub/core/protocols.py backend/tests/protocols.py"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)

    # The SDK protocols are likewise generated into the submodule from the core models here.
    exec_cmd = "git -C python_sdk diff --exit-code infrahub_sdk/protocols.py"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)

    _generate_custom_graphql_types(context=context)
    exec_cmd = "git diff --exit-code backend/infrahub/generators/graphql_queries/ backend/infrahub/computed_attribute/graphql_queries/"
    with context.cd(ESCAPED_REPO_PATH):
        context.run(exec_cmd)


@task(name="export-error-catalogue")
def export_error_catalogue(context: Context, output: str = "schema/error-catalogue.json") -> None:  # noqa: ARG001
    """Export the Infrahub error catalogue to a JSON Schema artefact."""
    from infrahub.errors.export import write_catalogue

    destination = Path(output)
    if not destination.is_absolute():
        destination = REPO_BASE / destination

    written = write_catalogue(destination)
    print(f" - [{NAMESPACE}] Wrote error catalogue to {written}")


def _generate_schemas(context: Context) -> None:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from infrahub.core.schema.definitions.internal import (
        attribute_schema,
        base_node_schema,
        generic_schema,
        node_schema,
        relationship_schema,
    )

    env = Environment(loader=FileSystemLoader(f"{REPO_BASE}/backend/templates"), undefined=StrictUndefined)
    generated = f"{REPO_BASE}/backend/infrahub/core/schema/generated"
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

    execute_command(context=context, command=f'ruff format "{generated}"')
    execute_command(context=context, command=f'ruff check --fix "{generated}"')

    _generate_schemas_sdk(context=context)


def _attribute_kinds_by_parameters(expected_parameters: set[str]) -> dict[str, list[str]]:
    """Group attribute kinds by the parameters model the backend selects for each.

    Deriving the grouping from the backend mapping keeps the generated discriminated union in
    step with it; the caller supplies the set of parameters models its variants cover.

    Raises:
        ValueError: If the backend mapping yields a parameters model set that differs from
            ``expected_parameters``, so the variant definitions are updated in lockstep.

    """
    from infrahub.core.schema.attribute_parameters import get_attribute_parameters_class_for_kind
    from infrahub.types import ATTRIBUTE_KIND_LABELS

    groups: dict[str, list[str]] = {}
    for attribute_kind in ATTRIBUTE_KIND_LABELS:
        groups.setdefault(get_attribute_parameters_class_for_kind(attribute_kind).__name__, []).append(attribute_kind)
    if set(groups) != expected_parameters:
        raise ValueError(
            "Attribute parameters mapping changed; update attribute_variant_specs to match: "
            f"{sorted(groups)} != {sorted(expected_parameters)}"
        )
    return groups


def _sdk_extension_field(name: str, annotation: str, default_definition: str, description: str) -> dict[str, str]:
    return {
        "name": name,
        "external_type_annotation": annotation,
        "external_default_definition": default_definition,
        "description": description,
        "external_pattern": "",
        "min": "",
        "max": "",
    }


def _sdk_extension_families(suffix: str) -> list[dict[str, Any]]:
    """Write-only models describing an extension of an existing node.

    Extension nodes are addressed by kind and carry the attributes and relationships to add,
    so they reuse the discriminated attribute union and the relationship model of the variant.
    """
    node_extension_fields = [
        _sdk_extension_field("kind", "str", "...", "Kind of the existing node to extend."),
        _sdk_extension_field(
            "attributes",
            f"list[AttributeSchema{suffix}]",
            "default_factory=list",
            "Attributes to add to the existing node.",
        ),
        _sdk_extension_field(
            "relationships",
            f"list[RelationshipSchema{suffix}]",
            "default_factory=list",
            "Relationships to add to the existing node.",
        ),
    ]
    return [
        {"class_name": f"NodeExtension{suffix}", "parent": "BaseModel", "attributes": node_extension_fields},
        {
            "class_name": f"SchemaExtension{suffix}",
            "parent": "BaseModel",
            "attributes": [
                _sdk_extension_field(
                    "nodes",
                    f"list[NodeExtension{suffix}]",
                    "default_factory=list",
                    "Nodes to extend with additional attributes and relationships.",
                ),
            ],
        },
    ]


def _sdk_root(suffix: str, with_version: bool, model_config_args: str, with_extensions: bool) -> dict[str, Any]:
    config_field = [f"model_config = ConfigDict({model_config_args})"] if model_config_args else []
    version_field = ["version: str | None = None"] if with_version else []
    extensions_field = [f"extensions: SchemaExtension{suffix} | None = None"] if with_extensions else []
    fields = [
        *config_field,
        *version_field,
        f"nodes: list[NodeSchema{suffix}] = Field(default_factory=list)",
        f"generics: list[GenericSchema{suffix}] = Field(default_factory=list)",
        *extensions_field,
    ]
    return {"class_name": f"InfrahubSchema{suffix}", "fields": fields}


def _sdk_base_node_family(base_node_schema: "SchemaNode", minimum: "Visibility", suffix: str) -> dict[str, Any]:
    """Base node family shared by node/generic/profile/template.

    Every node model exposes the derived ``kind`` (from namespace+name) on both write and read so
    attribute access works when reading a locally-authored schema. It only *serializes* on read:
    on write it is a plain property, so ``kind`` never round-trips into the write payload. The read
    variant additionally carries the server-computed ``hash`` field. All propagate to
    node/generic/profile/template via this base.
    """
    from infrahub.core.constants import UpdateSupport, Visibility
    from infrahub.core.schema.definitions.internal import SchemaAttribute

    attributes = [attribute for attribute in base_node_schema.attributes if attribute.visibility >= minimum]
    family: dict[str, Any] = {
        "class_name": f"BaseNodeSchema{suffix}",
        "parent": "BaseModel",
        "attributes": attributes,
        "computed_fields": [
            {
                "name": "kind",
                "return_type": "str",
                "expression": 'f"{self.namespace}{self.name}"',
                "serialize": minimum == Visibility.READ,
            }
        ],
    }
    if minimum == Visibility.READ:
        # `hash` is computed by the server and only exposed on read.
        hash_field = SchemaAttribute(
            name="hash",
            kind="Text",
            internal_kind=str,
            description="Hash of the node computed by the server.",
            optional=True,
            extra={"update": UpdateSupport.NOT_SUPPORTED, "visibility": Visibility.READ},
        )
        family["attributes"] = [*attributes, hash_field]
    return family


def _sdk_profile_template_families(suffix: str) -> list[dict[str, Any]]:
    """Read-only node families for profiles and templates (no write variant exists).

    Both are a base node plus the list of generics they inherit from, mirroring their internal
    counterparts; only the extra field is declared, the rest comes from the parent.
    """
    from infrahub.core.constants import UpdateSupport, Visibility
    from infrahub.core.schema.definitions.internal import SchemaAttribute

    def inherit_from(subject: str) -> SchemaAttribute:
        return SchemaAttribute(
            name="inherit_from",
            kind="List",
            internal_kind=str,
            default_factory="list",
            description=f"List of Generic Kind that this {subject} is inheriting from",
            optional=True,
            extra={"update": UpdateSupport.ALLOWED, "visibility": Visibility.READ},
        )

    return [
        {
            "class_name": f"ProfileSchema{suffix}",
            "parent": f"BaseNodeSchema{suffix}",
            "attributes": [inherit_from("profile")],
        },
        {
            "class_name": f"TemplateSchema{suffix}",
            "parent": f"BaseNodeSchema{suffix}",
            "attributes": [inherit_from("template")],
        },
    ]


# Values are sourced from ATTRIBUTE_KIND_LABELS to stay in step with the backend; the SDK's
# historical AttributeKind member names (e.g. MAC_ADDRESS) do not follow a single rule, so they
# are mapped explicitly here.
_ATTRIBUTE_KIND_MEMBER_NAMES = {
    "ID": "ID",
    "Dropdown": "DROPDOWN",
    "Text": "TEXT",
    "TextArea": "TEXTAREA",
    "DateTime": "DATETIME",
    "Email": "EMAIL",
    "Password": "PASSWORD",
    "HashedPassword": "HASHEDPASSWORD",
    "URL": "URL",
    "File": "FILE",
    "MacAddress": "MAC_ADDRESS",
    "Color": "COLOR",
    "Number": "NUMBER",
    "NumberPool": "NUMBERPOOL",
    "Bandwidth": "BANDWIDTH",
    "IPHost": "IPHOST",
    "IPNetwork": "IPNETWORK",
    "Boolean": "BOOLEAN",
    "Checkbox": "CHECKBOX",
    "List": "LIST",
    "JSON": "JSON",
    "Any": "ANY",
}


@dataclass(frozen=True)
class SdkEnumSpecs:
    """The (str, Enum) specs and discriminator lookups used to type the constrained SDK fields.

    ``enum_specs`` is the ordered ``name -> [(member, value)]`` mapping (its order sets the class
    order in the generated enums.py); the two ``*_value_to_member`` lookups map enum values back to
    member names for the attribute-kind and computed-attribute-kind discriminated unions.
    """

    enum_specs: dict[str, list[tuple[str, str]]]
    attribute_kind_value_to_member: dict[str, str]
    computed_kind_value_to_member: dict[str, str]


def _sdk_enum_specs() -> SdkEnumSpecs:
    """Build the dedicated (str, Enum) specs used to type the constrained SDK fields."""
    from enum import Enum

    from infrahub.core.constants import (
        AllowOverrideType,
        BranchSupportType,
        ComputedAttributeKind,
        HashableModelState,
        RelationshipCardinality,
        RelationshipDeleteBehavior,
        RelationshipDirection,
        RelationshipKind,
        SchemaAttributeDisplay,
    )
    from infrahub.types import ATTRIBUTE_KIND_LABELS

    def members(enum_cls: type[Enum]) -> list[tuple[str, str]]:
        return [(member.name, member.value) for member in enum_cls]

    attribute_kind_members = [(_ATTRIBUTE_KIND_MEMBER_NAMES[value], value) for value in ATTRIBUTE_KIND_LABELS]
    enum_specs: dict[str, list[tuple[str, str]]] = {
        "BranchSupportType": members(BranchSupportType),
        "RelationshipKind": members(RelationshipKind),
        "RelationshipCardinality": members(RelationshipCardinality),
        "RelationshipDirection": members(RelationshipDirection),
        "RelationshipDeleteBehavior": members(RelationshipDeleteBehavior),
        "AllowOverrideType": members(AllowOverrideType),
        "SchemaState": members(HashableModelState),
        "SchemaAttributeDisplay": members(SchemaAttributeDisplay),
        "ComputedAttributeKind": members(ComputedAttributeKind),
        "AttributeKind": attribute_kind_members,
    }
    return SdkEnumSpecs(
        enum_specs=enum_specs,
        attribute_kind_value_to_member={value: member for member, value in attribute_kind_members},
        computed_kind_value_to_member={value: member for member, value in members(ComputedAttributeKind)},
    )


def _sdk_kind_field(
    description: str, class_name: str, values: list[str], value_to_member: dict[str, str]
) -> dict[str, str]:
    """Render a discriminated-union ``kind`` field as a Literal of enum members.

    A Literal of enum members keeps the discriminator tied to the shared enum while still
    validating correctly under ``use_enum_values=True``.
    """
    members = ", ".join(f"{class_name}.{value_to_member[value]}" for value in values)
    return {
        "name": "kind",
        "external_type_annotation": f"Literal[{members}]",
        "external_default_definition": "...",
        "description": description,
        "external_pattern": "",
        "min": "",
        "max": "",
    }


def _render_sdk_enums(template: "Template", enum_specs: dict[str, list[tuple[str, str]]], generated: str) -> list[str]:
    """Render the self-contained enums module and return the sorted enum class names."""
    enums_rendered = template.render(
        enums=[
            {"name": name, "members": [(member, repr(value)) for member, value in members]}
            for name, members in enum_specs.items()
        ]
    )
    Path(f"{generated}/enums.py").write_text(enums_rendered, encoding="utf-8")
    return sorted(enum_specs)


def _write_sdk_generated_init(generated: str) -> None:
    init_content = (
        '# Generated by "invoke backend.generate", do not edit directly\n'
        "from . import enums, read, write\n\n"
        '__all__ = ["enums", "read", "write"]\n'
    )
    Path(f"{generated}/__init__.py").write_text(init_content, encoding="utf-8")


def _generate_schemas_sdk(context: Context) -> None:
    """Render the user-facing write/read schema models into the Python SDK.

    Both variants are produced from the same ``internal.py`` definitions by filtering each
    field on its ``visibility`` classification (write ⊆ read ⊆ internal). The output is
    self-contained (only pydantic + typing) so it imports with just the SDK installed.
    """
    import sys

    from jinja2 import Environment, FileSystemLoader, StrictUndefined

    from infrahub.core.constants import ComputedAttributeKind, UpdateSupport, Visibility
    from infrahub.core.schema.definitions.internal import (
        SchemaAttribute,
        SchemaNode,
        attribute_schema,
        base_node_schema,
        generic_schema,
        node_schema,
        relationship_schema,
    )

    env = Environment(loader=FileSystemLoader(f"{REPO_BASE}/backend/templates"), undefined=StrictUndefined)
    template = env.get_template("generate_schema_sdk.j2")
    enums_template = env.get_template("generate_schema_sdk_enums.j2")
    generated = f"{REPO_BASE}/python_sdk/infrahub_sdk/schema/generated"
    Path(generated).mkdir(parents=True, exist_ok=True)

    sdk_enums = _sdk_enum_specs()

    node_stripped = node_schema.without_duplicates(base_node_schema)
    generic_stripped = generic_schema.without_duplicates(base_node_schema)

    write_extra = {"update": UpdateSupport.ALLOWED, "visibility": Visibility.WRITE}

    def _field(
        name: str,
        kind: str,
        description: str,
        *,
        optional: bool = False,
        regex: str | None = None,
        enum: list[str] | None = None,
        default_value: int | None = None,
    ) -> SchemaAttribute:
        return SchemaAttribute(
            name=name,
            kind=kind,
            description=description,
            extra=write_extra,
            optional=optional,
            regex=regex,
            enum=enum,
            default_value=default_value,
        )

    # The attribute sub-blocks (choices, parameters, computed_attribute) are value models of their
    # own. They are emitted as dedicated data models so the write contract is explicit rather than
    # an opaque mapping. The attribute itself is a discriminated union on its kind: each variant
    # narrows kind to the kinds sharing one parameters shape and carries that parameters model, so a
    # given kind only validates against its own parameters. computed_attribute discriminates on its
    # own kind field.
    dropdown_choice_fields = [
        _field("name", "Text", "Name of the choice, must be unique within the dropdown."),
        _field("description", "Text", "Description of the choice.", optional=True),
        _field(
            "color",
            "Text",
            "Color of the choice, must be a valid HTML color code.",
            optional=True,
            regex=r"#[0-9a-fA-F]{6}\b",
        ),
        _field("label", "Text", "Human friendly representation of the choice.", optional=True),
    ]

    list_parameters_fields = [
        _field("regex", "Text", "Regular expression that each list item value must match if defined", optional=True),
    ]
    text_parameters_fields = [
        _field("regex", "Text", "Regular expression that attribute value must match if defined", optional=True),
        _field("min_length", "Number", "Set a minimum number of characters allowed.", optional=True),
        _field("max_length", "Number", "Set a maximum number of characters allowed.", optional=True),
    ]
    number_parameters_fields = [
        _field("min_value", "Number", "Set a minimum value allowed.", optional=True),
        _field("max_value", "Number", "Set a maximum value allowed.", optional=True),
        _field(
            "excluded_values",
            "Text",
            "List of values or range of values not allowed for the attribute, format is: '100,150-200,280,300-400'",
            optional=True,
            regex=r"^(\d+(?:-\d+)?)(?:,\d+(?:-\d+)?)*$",
        ),
    ]
    number_pool_parameters_fields = [
        _field("end_range", "Number", "End range for numbers for the associated NumberPool", default_value=sys.maxsize),
        _field("start_range", "Number", "Start range for numbers for the associated NumberPool", default_value=1),
        _field(
            "number_pool_id",
            "Text",
            "The ID of the numberpool associated with this attribute. "
            "Only set after the number pool has been provisioned.",
            optional=True,
        ),
    ]

    computed_kind_description = "Defines how the value of the attribute is computed."

    def _computed_kind_field(value: str) -> dict[str, str]:
        return _sdk_kind_field(
            computed_kind_description, "ComputedAttributeKind", [value], sdk_enums.computed_kind_value_to_member
        )

    computed_user_fields = [
        _computed_kind_field(ComputedAttributeKind.USER.value),
    ]
    computed_jinja2_fields = [
        _computed_kind_field(ComputedAttributeKind.JINJA2.value),
        _field("jinja2_template", "Text", "Jinja2 template used to compute the value, required when kind is Jinja2."),
    ]
    computed_transform_fields = [
        _computed_kind_field(ComputedAttributeKind.TRANSFORM_PYTHON.value),
        _field("transform", "Text", "Python transform name or ID, required when kind is TransformPython."),
    ]

    # The attribute is modelled as a discriminated union on kind. Each variant narrows kind to the
    # set of kinds the backend maps to one parameters shape, and carries that parameters model. The
    # kind -> parameters split is derived from the backend mapping so the union stays in step with
    # it; the generic variant absorbs every kind not claimed by a specific one. Order sets the union
    # member order. Second element is the backend parameters class name (SDK class = name + suffix).
    attribute_variant_specs: list[tuple[str, str]] = [
        ("TextAttribute", "TextAttributeParameters"),
        ("NumberAttribute", "NumberAttributeParameters"),
        ("ListAttribute", "ListAttributeParameters"),
        ("NumberPoolAttribute", "NumberPoolParameters"),
        ("GenericAttribute", "AttributeParameters"),
    ]
    kinds_by_parameters = _attribute_kinds_by_parameters({parameters for _, parameters in attribute_variant_specs})

    kind_description = next(attr for attr in attribute_schema.attributes if attr.name == "kind").description
    parameters_source = next(attr for attr in attribute_schema.attributes if attr.name == "parameters")

    def _visible(node: SchemaNode, minimum: Visibility) -> list[Any]:
        return [attribute for attribute in node.attributes if attribute.visibility >= minimum]

    def _parameters_field(parameters_name: str) -> dict[str, str]:
        return {
            "name": "parameters",
            "external_type_annotation": f"{parameters_name}__VARIANT__ | None",
            "external_default_definition": parameters_source.external_default_definition,
            "description": parameters_source.description,
            "external_pattern": parameters_source.external_pattern,
            "min": parameters_source.min,
            "max": parameters_source.max,
        }

    def _attribute_variant_families(minimum: Visibility, suffix: str) -> list[dict[str, Any]]:
        base_name = f"AttributeSchemaBase{suffix}"
        base_fields = [attribute for attribute in _visible(attribute_schema, minimum) if attribute.name != "parameters"]
        families: list[dict[str, Any]] = [{"class_name": base_name, "parent": "BaseModel", "attributes": base_fields}]
        for variant, parameters_name in attribute_variant_specs:
            kind_field = _sdk_kind_field(
                kind_description,
                "AttributeKind",
                kinds_by_parameters[parameters_name],
                sdk_enums.attribute_kind_value_to_member,
            )
            families.append(
                {
                    "class_name": f"{variant}{suffix}",
                    "parent": base_name,
                    "attributes": [kind_field, _parameters_field(parameters_name)],
                }
            )
        return families

    def _pre_families(minimum: Visibility, suffix: str) -> list[dict[str, Any]]:
        base = f"AttributeParameters{suffix}"
        return [
            {"class_name": base, "parent": "BaseModel", "attributes": []},
            {"class_name": f"ListAttributeParameters{suffix}", "parent": base, "attributes": list_parameters_fields},
            {"class_name": f"TextAttributeParameters{suffix}", "parent": base, "attributes": text_parameters_fields},
            {
                "class_name": f"NumberAttributeParameters{suffix}",
                "parent": base,
                "attributes": number_parameters_fields,
            },
            {
                "class_name": f"NumberPoolParameters{suffix}",
                "parent": base,
                "attributes": number_pool_parameters_fields,
            },
            {"class_name": f"DropdownChoice{suffix}", "parent": "BaseModel", "attributes": dropdown_choice_fields},
            {
                "class_name": f"ComputedAttributeUser{suffix}",
                "parent": "BaseModel",
                "attributes": computed_user_fields,
            },
            {
                "class_name": f"ComputedAttributeJinja2{suffix}",
                "parent": "BaseModel",
                "attributes": computed_jinja2_fields,
            },
            {
                "class_name": f"ComputedAttributeTransformPython{suffix}",
                "parent": "BaseModel",
                "attributes": computed_transform_fields,
            },
            *_attribute_variant_families(minimum, suffix),
        ]

    def _aliases(suffix: str) -> list[str]:
        variant_members = "".join(f"        {variant}{suffix},\n" for variant, _ in attribute_variant_specs)
        return [
            (
                f"ComputedAttribute{suffix} = Annotated[\n"
                f"    Union[\n"
                f"        ComputedAttributeUser{suffix},\n"
                f"        ComputedAttributeJinja2{suffix},\n"
                f"        ComputedAttributeTransformPython{suffix},\n"
                f"    ],\n"
                f'    Field(discriminator="kind"),\n'
                "]"
            ),
            (
                f"AttributeSchema{suffix} = Annotated[\n"
                f"    Union[\n"
                f"{variant_members}"
                f"    ],\n"
                f'    Field(discriminator="kind"),\n'
                "]"
            ),
        ]

    def _families(minimum: Visibility, suffix: str) -> list[dict[str, Any]]:
        return [
            {
                "class_name": f"RelationshipSchema{suffix}",
                "parent": "BaseModel",
                "attributes": _visible(relationship_schema, minimum),
            },
            _sdk_base_node_family(base_node_schema, minimum, suffix),
            {
                "class_name": f"NodeSchema{suffix}",
                "parent": f"BaseNodeSchema{suffix}",
                "attributes": _visible(node_stripped, minimum),
            },
            {
                "class_name": f"GenericSchema{suffix}",
                "parent": f"BaseNodeSchema{suffix}",
                "attributes": _visible(generic_stripped, minimum),
            },
        ]

    # use_enum_values keeps runtime field values as plain strings even though fields are typed
    # with the dedicated enums, so equality against strings and serialization stay unchanged.
    enum_names = _render_sdk_enums(enums_template, sdk_enums.enum_specs, generated)

    # Each variant carries an extra-families builder for the models unique to it: the write
    # variant adds the extension models, the read variant adds the profile/template projections.
    # Both variants expose ``kind`` as a property, but only the read variant serializes it (via
    # ``@computed_field``), so only the read variant imports ``computed_field``.
    variants = {
        "write": (
            Visibility.WRITE,
            'extra="ignore", use_enum_values=True',
            "Write",
            True,
            _sdk_extension_families,
            False,
        ),
        "read": (Visibility.READ, 'extra="ignore", use_enum_values=True', "Read", False, _sdk_profile_template_families, True),
    }
    for variant, (
        minimum,
        model_config_args,
        suffix,
        with_version,
        extra_families,
        with_computed_field,
    ) in variants.items():
        rendered = template.render(
            pre_families=_pre_families(minimum, suffix),
            aliases=_aliases(suffix),
            families=_families(minimum, suffix) + extra_families(suffix),
            model_config_args=model_config_args,
            root=_sdk_root(suffix, with_version, model_config_args, with_extensions=variant == "write"),
            enum_names=enum_names,
            with_computed_field=with_computed_field,
        )
        rendered = rendered.replace("__VARIANT__", suffix)
        Path(f"{generated}/{variant}.py").write_text(rendered, encoding="utf-8")

    _write_sdk_generated_init(generated)

    execute_command(context=context, command=f'ruff format "{generated}"')
    execute_command(context=context, command=f'ruff check --fix "{generated}"')


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


def _jinja2_filter_render_relationship(value: dict[str, Any]) -> str:
    peer = value.get("peer", "")
    name = value["name"]
    if peer:
        return f"{name}: RelationshipManager[{peer}]"
    return f"{name}: RelationshipManager"


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
    sys.path.insert(0, f"{REPO_BASE}/backend")
    from tests.helpers.schema import test_models

    env = Environment(loader=FileSystemLoader(f"{REPO_BASE}/backend/templates"), undefined=StrictUndefined)
    env.filters["inheritance"] = _jinja2_filter_inheritance
    env.filters["render_attribute"] = _jinja2_filter_render_attribute
    env.filters["render_relationship"] = _jinja2_filter_render_relationship

    # Export protocols for backend code use
    generated = f"{REPO_BASE}/backend/infrahub/core"
    template = env.get_template("generate_protocols.j2")

    protocols_rendered = template.render(
        generics=_sort_and_filter_models(core_models["generics"]), models=_sort_and_filter_models(core_models["nodes"])
    )
    protocols_output = f"{generated}/protocols.py"
    Path(protocols_output).write_text(protocols_rendered, encoding="utf-8")

    execute_command(context=context, command=f"ruff format {protocols_output}")
    execute_command(context=context, command=f"ruff check --fix {protocols_output}")

    # Export test protocols for backend code use
    generated = f"{REPO_BASE}/backend/tests/"

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
    generated = f"{REPO_BASE}/python_sdk/infrahub_sdk"
    template = env.get_template("generate_protocols_sdk.j2")

    protocols_rendered = template.render(
        generics=_sort_and_filter_models(core_models["generics"]), models=_sort_and_filter_models(core_models["nodes"])
    )
    protocols_output = f"{generated}/protocols.py"
    Path(protocols_output).write_text(protocols_rendered, encoding="utf-8")

    execute_command(context=context, command=f"ruff format {protocols_output}")
    execute_command(context=context, command=f"ruff check --fix {protocols_output}")
