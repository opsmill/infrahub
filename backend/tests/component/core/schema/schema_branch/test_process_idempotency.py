import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase

LOCATION_GENERIC = GenericSchema(
    name="Location",
    namespace="Test",
    label="Location",
    hierarchical=True,
    include_in_menu=True,
    default_filter="name__value",
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="description", kind="Text", optional=True),
    ],
)

NETWORK_ELEMENT_GENERIC = GenericSchema(
    name="NetworkElement",
    namespace="Test",
    label="Network Element",
    include_in_menu=True,
    attributes=[
        AttributeSchema(name="description", kind="Text", optional=True),
    ],
)

CONTINENT_NODE = NodeSchema(
    name="Continent",
    namespace="Test",
    label="Continent",
    include_in_menu=True,
    default_filter="name__value",
    inherit_from=["TestLocation"],
    parent="",
    children="TestCountry",
    generate_profile=True,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
    ],
)

COUNTRY_NODE = NodeSchema(
    name="Country",
    namespace="Test",
    label="Country",
    include_in_menu=True,
    default_filter="name__value",
    inherit_from=["TestLocation"],
    parent="TestContinent",
    children="TestSite",
    generate_profile=True,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="iso_code", kind="Text", optional=True),
    ],
)

SITE_NODE = NodeSchema(
    name="Site",
    namespace="Test",
    label="Site",
    include_in_menu=True,
    default_filter="name__value",
    inherit_from=["TestLocation"],
    parent="TestCountry",
    children="",
    generate_profile=True,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="address", kind="Text", optional=True),
    ],
)

DEVICE_NODE = NodeSchema(
    name="Device",
    namespace="Test",
    label="Device",
    include_in_menu=True,
    default_filter="name__value",
    generate_profile=True,
    generate_template=True,
    inherit_from=["TestNetworkElement"],
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="role", kind="Text", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="site",
            peer="TestSite",
            kind=RelationshipKind.ATTRIBUTE,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        ),
        RelationshipSchema(
            name="interfaces",
            peer="TestInterface",
            kind=RelationshipKind.COMPONENT,
            cardinality=RelationshipCardinality.MANY,
            optional=True,
        ),
    ],
)

INTERFACE_NODE = NodeSchema(
    name="Interface",
    namespace="Test",
    label="Interface",
    include_in_menu=True,
    default_filter="name__value",
    generate_profile=True,
    generate_template=True,
    inherit_from=["TestNetworkElement"],
    attributes=[
        AttributeSchema(name="name", kind="Text"),
        AttributeSchema(name="speed", kind="Number", optional=True),
        AttributeSchema(name="enabled", kind="Boolean", default_value=True),
    ],
    relationships=[
        RelationshipSchema(
            name="device",
            peer="TestDevice",
            kind=RelationshipKind.PARENT,
            cardinality=RelationshipCardinality.ONE,
            optional=False,
        ),
    ],
)


@pytest.fixture
def idempotency_schema() -> SchemaRoot:
    return SchemaRoot(
        nodes=[CONTINENT_NODE, COUNTRY_NODE, SITE_NODE, DEVICE_NODE, INTERFACE_NODE],
        generics=[LOCATION_GENERIC, NETWORK_ELEMENT_GENERIC],
    )


def _describe_hash_diff(before: SchemaBranch, after: SchemaBranch) -> str:
    """Compare two SchemaBranch instances and return a human-readable diff description.

    Useful for diagnosing hash mismatches. Compares per-schema model fields for all
    nodes and generics, reporting only the fields that differ.
    """
    lines: list[str] = []
    all_names = sorted(set(before.node_names + before.generic_names + after.node_names + after.generic_names))
    for name in all_names:  # noqa: PLR1702
        try:
            obj_before = before.get(name=name, duplicate=False)
            dump_before = obj_before.model_dump()
        except Exception:
            lines.append(f"{name}: only in 'after'")
            continue
        try:
            obj_after = after.get(name=name, duplicate=False)
            dump_after = obj_after.model_dump()
        except Exception:
            lines.append(f"{name}: only in 'before'")
            continue
        if obj_before.get_hash() == obj_after.get_hash():
            continue
        lines.append(f"{name}:")
        for key in sorted(set(dump_before.keys()) | set(dump_after.keys())):
            v1, v2 = dump_before.get(key), dump_after.get(key)
            if v1 == v2:
                continue
            if key not in ("attributes", "relationships"):
                lines.append(f"  {key}: {v1!r} -> {v2!r}")
                continue
            items1 = {i["name"]: i for i in v1} if v1 else {}
            items2 = {i["name"]: i for i in v2} if v2 else {}
            for iname in sorted(set(items1.keys()) | set(items2.keys())):
                i1, i2 = items1.get(iname), items2.get(iname)
                if i1 == i2:
                    continue
                if i1 is None:
                    lines.append(f"  {key}.{iname}: ADDED")
                elif i2 is None:
                    lines.append(f"  {key}.{iname}: REMOVED")
                else:
                    for fk in sorted(set(i1.keys()) | set(i2.keys())):
                        if i1.get(fk) != i2.get(fk):
                            lines.append(f"  {key}.{iname}.{fk}: {i1.get(fk)!r} -> {i2.get(fk)!r}")
    return "\n".join(lines) if lines else "(no per-schema diffs found)"


def test_process_idempotency(register_core_models_schema: SchemaBranch, idempotency_schema: SchemaRoot) -> None:
    """Calling process() twice on the same SchemaBranch produces an identical hash."""
    schema_branch = register_core_models_schema
    schema_branch.load_schema(schema=idempotency_schema)
    schema_branch.process()

    hash_after_first = schema_branch.get_hash()
    nodes_after_first = sorted(schema_branch.node_names)
    generics_after_first = sorted(schema_branch.generic_names)
    profiles_after_first = sorted(schema_branch.profile_names)
    templates_after_first = sorted(schema_branch.template_names)

    snapshot = schema_branch.duplicate()

    schema_branch.process()

    hash_after_second = schema_branch.get_hash()
    nodes_after_second = sorted(schema_branch.node_names)
    generics_after_second = sorted(schema_branch.generic_names)
    profiles_after_second = sorted(schema_branch.profile_names)
    templates_after_second = sorted(schema_branch.template_names)

    assert hash_after_first == hash_after_second, (
        f"get_hash() changed after second process()\n{_describe_hash_diff(snapshot, schema_branch)}"
    )
    assert nodes_after_first == nodes_after_second, "node names changed after second process()"
    assert generics_after_first == generics_after_second, "generic names changed after second process()"
    assert profiles_after_first == profiles_after_second, "profile names changed after second process()"
    assert templates_after_first == templates_after_second, "template names changed after second process()"


async def test_process_idempotency_after_db_roundtrip(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    register_builtin_models_schema: SchemaBranch,
    idempotency_schema: SchemaRoot,
) -> None:
    """Schema loaded, saved to DB, reloaded, and processed produces the same hash."""
    schema_after_register = registry.schema.register_schema(schema=idempotency_schema, branch=default_branch.name)

    # load_schema_to_db mutates schema_after_register in-place (assigns DB ids),
    # so capture the hash after the save, not before.
    await registry.schema.load_schema_to_db(schema=schema_after_register, db=db, branch=default_branch)
    hash_after_save = schema_after_register.get_hash()

    # load_schema_from_db calls process() internally
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    loaded_schema = schema_branch.duplicate()
    await registry.schema.load_schema_from_db(db=db, branch=default_branch, schema=loaded_schema)

    hash_after_reload = loaded_schema.get_hash()

    assert hash_after_save == hash_after_reload, (
        f"Hash mismatch after DB roundtrip.\n"
        f"  After save:   {hash_after_save}\n"
        f"  After reload: {hash_after_reload}\n"
        f"{_describe_hash_diff(schema_after_register, loaded_schema)}"
    )

    diff = schema_after_register.diff(other=loaded_schema)
    assert not diff.all, f"Unexpected diff after DB roundtrip: {diff.all}"
