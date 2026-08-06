import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.initialization import create_branch
from infrahub.core.models import HashableModelDiff, SchemaDiff
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import SchemaNotFoundError

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


# Standalone nodes carrying generated kinds, one per schema change so no change touches
# a kind another change depends on
GADGET_NODE = NodeSchema(
    name="Gadget",
    namespace="Test",
    label="Gadget",
    include_in_menu=True,
    default_filter="name__value",
    generate_profile=True,
    generate_template=True,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
    ],
)

DOODAD_NODE = NodeSchema(
    name="Doodad",
    namespace="Test",
    label="Doodad",
    include_in_menu=True,
    default_filter="name__value",
    generate_profile=True,
    generate_template=True,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
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
        except SchemaNotFoundError:
            lines.append(f"{name}: only in 'after'")
            continue
        try:
            obj_after = after.get(name=name, duplicate=False)
            dump_after = obj_after.model_dump()
        except SchemaNotFoundError:
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


class TestSchemaBranchDbRoundtrip:
    """Schema changes saved to the database must reload into the schema that produced them.

    The base schema is saved once for the whole class; each test applies its own change on its
    own branch, so only the changed kind is written and the changes stay independent of each
    other and of the order they run in.
    """

    @pytest.fixture(scope="class")
    async def saved_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> SchemaBranch:
        """Register and persist the base schema once, and return it as saved."""
        schema_root = SchemaRoot(
            nodes=[CONTINENT_NODE, COUNTRY_NODE, SITE_NODE, DEVICE_NODE, INTERFACE_NODE, GADGET_NODE, DOODAD_NODE],
            generics=[LOCATION_GENERIC, NETWORK_ELEMENT_GENERIC],
        )
        schema = registry.schema.register_schema(schema=schema_root, branch=default_branch_scope_class.name)
        # load_schema_to_db mutates the schema in place to assign DB ids, so the saved state is
        # only final once it returns
        await registry.schema.load_schema_to_db(schema=schema, db=db, branch=default_branch_scope_class)
        return schema

    async def test_reload_matches_saved_schema(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, saved_schema: SchemaBranch
    ) -> None:
        """Loading the saved schema into an empty branch reproduces it exactly."""
        loaded_schema = await registry.schema.load_schema_from_db(
            db=db,
            branch=default_branch_scope_class,
            schema=SchemaBranch(cache={}, name=default_branch_scope_class.name),
        )

        assert loaded_schema.get_hash() == saved_schema.get_hash(), (
            f"Hash mismatch after DB roundtrip.\n{_describe_hash_diff(saved_schema, loaded_schema)}"
        )
        assert sorted(loaded_schema.node_names) == sorted(saved_schema.node_names)
        assert sorted(loaded_schema.generic_names) == sorted(saved_schema.generic_names)
        assert sorted(loaded_schema.profile_names) == sorted(saved_schema.profile_names)
        assert sorted(loaded_schema.template_names) == sorted(saved_schema.template_names)
        assert not saved_schema.diff(other=loaded_schema).all

    async def test_disabling_generate_template_drops_template(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, saved_schema: SchemaBranch
    ) -> None:
        """Turning generate_template off drops the template on a schema that still holds it.

        The stale schema stands in for a worker that has not yet seen the change.
        """
        branch = await create_branch(branch_name="disable-generate-template", db=db)
        stale_schema = registry.schema.get_schema_branch(name=branch.name).duplicate()
        assert "TemplateTestDoodad" in stale_schema.template_names

        candidate_schema = registry.schema.get_schema_branch(name=branch.name)
        doodad = candidate_schema.get_node(name="TestDoodad", duplicate=True)
        doodad.generate_template = False
        candidate_schema.set(name="TestDoodad", schema=doodad)
        await registry.schema.update_schema_branch(
            schema=candidate_schema,
            db=db,
            branch=branch,
            diff=SchemaDiff(changed={"TestDoodad": HashableModelDiff(changed={"generate_template": None})}),
        )
        updated_schema = registry.schema.get_schema_branch(name=branch.name)

        assert "TestDoodad" in updated_schema.node_names
        assert "TemplateTestDoodad" not in updated_schema.template_names
        assert "ProfileTestDoodad" in updated_schema.profile_names

        schema_diff = stale_schema.get_hash_full().compare(updated_schema.get_hash_full())
        assert schema_diff is not None
        assert schema_diff.changed_nodes == ["TestDoodad"]

        refreshed_schema = await registry.schema.load_schema_from_db(
            db=db, branch=branch, schema=stale_schema, schema_diff=schema_diff
        )

        assert refreshed_schema.get_hash() == updated_schema.get_hash(), (
            f"Hash mismatch after disabling generate_template.\n{_describe_hash_diff(updated_schema, refreshed_schema)}"
        )
        assert "TemplateTestDoodad" not in refreshed_schema.template_names
        assert sorted(refreshed_schema.template_names) == sorted(updated_schema.template_names)
        assert sorted(refreshed_schema.profile_names) == sorted(updated_schema.profile_names)

    async def test_removing_node_drops_its_generated_kinds(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, saved_schema: SchemaBranch
    ) -> None:
        """Removing a node with generated kinds reloads into a schema without any of them.

        Removing the kind leaves the template and profile generated from it without an owner
        until the schema is reprocessed, which is the state a refreshing worker starts from.
        """
        branch = await create_branch(branch_name="remove-generated-kinds", db=db)
        candidate_schema = registry.schema.get_schema_branch(name=branch.name)
        assert "TemplateTestGadget" in candidate_schema.template_names
        assert "ProfileTestGadget" in candidate_schema.profile_names

        await registry.schema.update_schema_branch(
            schema=candidate_schema,
            db=db,
            branch=branch,
            diff=SchemaDiff(removed={"TestGadget": HashableModelDiff()}),
        )
        updated_schema = registry.schema.get_schema_branch(name=branch.name)

        assert "TestGadget" not in updated_schema.node_names
        assert "TemplateTestGadget" not in updated_schema.template_names
        assert "ProfileTestGadget" not in updated_schema.profile_names

        reloaded_schema = await registry.schema.load_schema_from_db(
            db=db, branch=branch, schema=SchemaBranch(cache={}, name=branch.name)
        )

        assert reloaded_schema.get_hash() == updated_schema.get_hash(), (
            f"Hash mismatch after removing a node with generated kinds.\n"
            f"{_describe_hash_diff(updated_schema, reloaded_schema)}"
        )
        assert sorted(reloaded_schema.node_names) == sorted(updated_schema.node_names)
        assert sorted(reloaded_schema.generic_names) == sorted(updated_schema.generic_names)
        assert sorted(reloaded_schema.profile_names) == sorted(updated_schema.profile_names)
        assert sorted(reloaded_schema.template_names) == sorted(updated_schema.template_names)
        assert not updated_schema.diff(other=reloaded_schema).all
