from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import BranchSupportType, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.dropdown import DropdownChoice
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch


def _describe_hash_diff(before: SchemaBranch, after: SchemaBranch) -> str:
    """Render a per-schema diff report when hashes disagree.

    Covers nodes, generics, profiles, and templates, since SchemaBranch.get_hash()
    only covers nodes + generics.
    """
    lines: list[str] = []
    all_names = sorted(
        set(
            before.node_names
            + before.generic_names
            + before.profile_names
            + before.template_names
            + after.node_names
            + after.generic_names
            + after.profile_names
            + after.template_names
        )
    )
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


def _validate_process_idempotent(schema_branch: SchemaBranch, iterations: int = 4) -> None:
    """Call process() once to establish baseline, then `iterations` more times
    asserting the full schema state is unchanged across calls.

    Checks the schema hash (nodes + generics), node/generic/template/profile
    name sets, and each template and profile hash individually — since
    SchemaBranch.get_hash() only covers nodes and generics.
    """
    schema_branch.process()

    hash_initial = schema_branch.get_hash()
    node_names_initial = set(schema_branch.node_names)
    generic_names_initial = set(schema_branch.generic_names)
    template_names_initial = set(schema_branch.template_names)
    profile_names_initial = set(schema_branch.profile_names)

    template_hashes_initial = {
        name: schema_branch.get(name=name, duplicate=False).get_hash() for name in template_names_initial
    }
    profile_hashes_initial = {
        name: schema_branch.get(name=name, duplicate=False).get_hash() for name in profile_names_initial
    }

    snapshot = schema_branch.duplicate()

    for iteration in range(2, 2 + iterations):
        schema_branch.process()

        assert schema_branch.get_hash() == hash_initial, (
            f"SchemaBranch hash (nodes + generics) changed at process() call #{iteration}.\n"
            f"{_describe_hash_diff(snapshot, schema_branch)}"
        )
        assert set(schema_branch.node_names) == node_names_initial, f"node_names changed at process() call #{iteration}"
        assert set(schema_branch.generic_names) == generic_names_initial, (
            f"generic_names changed at process() call #{iteration}"
        )
        assert set(schema_branch.template_names) == template_names_initial, (
            f"template_names changed at process() call #{iteration}"
        )
        assert set(schema_branch.profile_names) == profile_names_initial, (
            f"profile_names changed at process() call #{iteration}"
        )

        for name in template_names_initial:
            current = schema_branch.get(name=name, duplicate=False).get_hash()
            assert current == template_hashes_initial[name], (
                f"Template {name} hash changed at process() call #{iteration}.\n"
                f"{_describe_hash_diff(snapshot, schema_branch)}"
            )
        for name in profile_names_initial:
            current = schema_branch.get(name=name, duplicate=False).get_hash()
            assert current == profile_hashes_initial[name], (
                f"Profile {name} hash changed at process() call #{iteration}.\n"
                f"{_describe_hash_diff(snapshot, schema_branch)}"
            )


@pytest.fixture
def firewall_hfid_schema() -> SchemaRoot:
    """FirewallGenericDevice.name is implicitly unique because it is the only item in the HFID.

    Before fix, this took multiple runs through SchemaBranch.process() to filter through and set
    inheriting schema DcimFirewall.name to unique, which eventually removes the attribute
    from the generated TemplateSchema.
    """
    return SchemaRoot(
        version="1.0",
        generics=[
            GenericSchema(
                name="GenericDevice",
                namespace="Firewall",
                description="Generic Firewall object.",
                include_in_menu=False,
                order_by=["name__value"],
                display_label="{{ name__value }}",
                human_friendly_id=["name__value"],
                attributes=[AttributeSchema(name="name", kind="Text")],
            ),
            GenericSchema(
                name="GenericRules",
                namespace="Firewall",
                description="Generic Generic Rules object.",
                human_friendly_id=["rule_id__value"],
                display_label="{{ rule_id__value }}",
                include_in_menu=False,
                order_by=["rule_id__value"],
                attributes=[
                    AttributeSchema(
                        name="rule_id",
                        kind="NumberPool",  # trigger #1
                        read_only=True,
                        branch=BranchSupportType.AGNOSTIC,
                    ),
                ],
            ),
        ],
        nodes=[
            NodeSchema(
                name="Firewall",
                namespace="Dcim",
                label="Firewall",
                include_in_menu=False,
                generate_template=True,  # trigger #2
                inherit_from=["FirewallGenericDevice"],
                attributes=[
                    AttributeSchema(
                        name="status",
                        kind="Dropdown",
                        optional=True,
                        order_weight=1100,
                        choices=[
                            DropdownChoice(name="active", label="Active", color="#7fbf7f"),
                            DropdownChoice(name="provisioning", label="Provisioning", color="#ffff7f"),
                            DropdownChoice(name="maintenance", label="Maintenance", color="#ffd27f"),
                            DropdownChoice(name="drained", label="Drained", color="#bfbfbf"),
                        ],
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def conflicting_inherit_schema() -> SchemaRoot:
    """A node inheriting the same attribute from two generics with conflicting `unique` settings.

    NodeInheritanceHandler iterates `inherit_from` in order. For the first generic, the attribute
    is added fresh; for each subsequent generic, `update_from_generic` overwrites every
    non-excluded field on the existing inherited attribute. With
    inherit_from=[TestGenericSpecific, TestGenericBase]: TestGenericSpecific adds `name` with
    unique=False, then TestGenericBase's update_from_generic flips it to unique=True.
    """
    return SchemaRoot(
        generics=[
            GenericSchema(
                name="GenericBase",
                namespace="Test",
                description="Base generic with a unique name attribute.",
                include_in_menu=False,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
            GenericSchema(
                name="GenericSpecific",
                namespace="Test",
                description="Specific generic with a non-unique name attribute.",
                include_in_menu=False,
                attributes=[AttributeSchema(name="name", kind="Text")],
            ),
        ],
        nodes=[
            NodeSchema(
                name="ConcreteDevice",
                namespace="Test",
                description="Node inheriting name from two generics with conflicting unique settings.",
                include_in_menu=False,
                generate_template=True,
                # TestGenericSpecific processed first (name.unique=False),
                # then update_from_generic overwrites to unique=True from TestGenericBase.
                inherit_from=["TestGenericSpecific", "TestGenericBase"],
            ),
        ],
    )


@pytest.fixture
def local_override_inherited_schema() -> SchemaRoot:
    """Node locally declares an attribute that is also defined on an inherited generic.

    Attributes have different values for `unique`
    """
    return SchemaRoot(
        generics=[
            GenericSchema(
                name="GenericThing",
                namespace="Test",
                description="Generic with a unique name attribute.",
                include_in_menu=False,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
        ],
        nodes=[
            NodeSchema(
                name="LocalThing",
                namespace="Test",
                description="Node that locally overrides the inherited name attr to be non-unique.",
                include_in_menu=False,
                generate_template=True,
                inherit_from=["TestGenericThing"],
                # Local declaration of `name` with unique=False — should suppress the
                # generic's unique=True version of the same attribute.
                attributes=[AttributeSchema(name="name", kind="Text", unique=False)],
            ),
        ],
    )


@pytest.fixture
def multi_generic_conflicting_optional_schema() -> SchemaRoot:
    """Node inherits from two generics that share an attribute with conflicting non-unique fields.

    Different values in the two attributes for `optional`, `default_value`, `branch`,
    `max_length`
    """
    return SchemaRoot(
        generics=[
            GenericSchema(
                name="GenericPermissive",
                namespace="Test",
                description="Generic with optional name and a default value.",
                include_in_menu=False,
                attributes=[
                    AttributeSchema(
                        name="name",
                        kind="Text",
                        optional=True,
                        default_value="permissive-default",
                        max_length=50,
                        branch=BranchSupportType.LOCAL,
                    ),
                ],
            ),
            GenericSchema(
                name="GenericStrict",
                namespace="Test",
                description="Generic with mandatory name and no default value.",
                include_in_menu=False,
                attributes=[
                    AttributeSchema(
                        name="name",
                        kind="Text",
                        optional=False,
                        max_length=10,
                        branch=BranchSupportType.AGNOSTIC,
                    ),
                ],
            ),
        ],
        nodes=[
            NodeSchema(
                name="Combined",
                namespace="Test",
                description="Node inheriting `name` from two generics with conflicting non-unique fields.",
                include_in_menu=False,
                generate_template=True,
                # GenericPermissive processed first; GenericStrict's update_from_generic
                # then overwrites optional, default_value, max_length, branch.
                inherit_from=["TestGenericPermissive", "TestGenericStrict"],
            ),
        ],
    )


@pytest.fixture
def read_only_attribute_schema() -> SchemaRoot:
    """Node with `generate_template=True` inheriting an attribute marked `read_only=True`.

    `read_only` affects attribute inclusion in Template and Profile schemas. this test case
    ensures there is no drift like we have seen with the `unique` property
    """
    return SchemaRoot(
        generics=[
            GenericSchema(
                name="GenericReadable",
                namespace="Test",
                description="Generic with a read-only attribute.",
                include_in_menu=False,
                attributes=[
                    AttributeSchema(name="serial", kind="Text", read_only=True),
                    AttributeSchema(name="description", kind="Text", optional=True),
                ],
            ),
        ],
        nodes=[
            NodeSchema(
                name="ReadOnlyDevice",
                namespace="Test",
                description="Node inheriting a read-only attr; templates must exclude it stably.",
                include_in_menu=False,
                generate_template=True,
                inherit_from=["TestGenericReadable"],
            ),
        ],
    )


@pytest.fixture
def hfid_from_unique_attrs_schema() -> SchemaRoot:
    """Node has `unique=True` on an attribute but no HFID.

    Unique attribute with no HFID or uniqueness_constraints ensures that HFID, uniqueness
    constraints, attribute uniqueness, and inheritance don't interact to cause drift
    """
    return SchemaRoot(
        generics=[
            GenericSchema(
                name="GenericHasUnique",
                namespace="Test",
                description="Generic with a unique attribute and no HFID.",
                include_in_menu=False,
                attributes=[
                    AttributeSchema(name="key", kind="Text", unique=True),
                    AttributeSchema(name="extra", kind="Text", optional=True),
                ],
            ),
        ],
        nodes=[
            NodeSchema(
                name="DerivedFromUnique",
                namespace="Test",
                description="Node with no HFID, relying on inherited unique attr to derive one.",
                include_in_menu=False,
                generate_template=True,
                inherit_from=["TestGenericHasUnique"],
            ),
        ],
    )


@pytest.fixture
def hfid_from_constraints_schema() -> SchemaRoot:
    """Node has a single-attribute uniqueness_constraint but no HFID and no unique attrs.

    Lone uniqueness_constraint ensures that HFID, uniqueness constraints, attribute
    uniqueness, and inheritance don't interact to cause drift
    """
    return SchemaRoot(
        generics=[
            GenericSchema(
                name="GenericHasConstraint",
                namespace="Test",
                description="Generic with a uniqueness_constraint but no HFID.",
                include_in_menu=False,
                uniqueness_constraints=[["code__value"]],
                attributes=[
                    AttributeSchema(name="code", kind="Text"),
                    AttributeSchema(name="extra", kind="Text", optional=True),
                ],
            ),
        ],
        nodes=[
            NodeSchema(
                name="DerivedFromConstraint",
                namespace="Test",
                description="Node with no HFID, deriving one from the inherited constraint.",
                include_in_menu=False,
                generate_template=True,
                inherit_from=["TestGenericHasConstraint"],
            ),
        ],
    )


@pytest.fixture
def profile_excludes_relationship_in_constraint_schema() -> SchemaRoot:
    """Node has an HFID that crosses a relationship, putting the rel name in uniqueness_constraints."""
    return SchemaRoot(
        nodes=[
            NodeSchema(
                name="Site",
                namespace="Test",
                description="Site with a unique name (target of the HFID-traversed relationship).",
                include_in_menu=False,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
            NodeSchema(
                name="Rack",
                namespace="Test",
                description="Rack identified by site + rack_id; the `site` rel must be excluded from its profile.",
                include_in_menu=False,
                generate_template=True,
                human_friendly_id=["site__name__value", "rack_id__value"],
                attributes=[
                    AttributeSchema(name="rack_id", kind="Text"),
                    AttributeSchema(name="description", kind="Text", optional=True),
                ],
                relationships=[
                    RelationshipSchema(
                        name="site",
                        peer="TestSite",
                        kind=RelationshipKind.ATTRIBUTE,
                        cardinality=RelationshipCardinality.ONE,
                        optional=False,
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def template_relationship_peer_resolution_schema() -> SchemaRoot:
    """Node with `generate_template=True` and relationships of multiple kinds.

    a template's relationship peer is based on `relationship.kind` and whether `relationship.peer`
    is in SUBTEMPLATE_EXCLUDED_KINDS:
      - kind in (ATTRIBUTE, GENERIC) -> peer kept as-is
      - peer in SUBTEMPLATE_EXCLUDED_KINDS -> peer kept as-is
      - otherwise (COMPONENT, PARENT) -> peer rewritten to Template{peer}

    Any drift in `relationship.kind` or in the peer's classification between passes
    would flip which branch is taken. This fixture exercises the rewrite vs keep
    paths in a single template.
    """
    return SchemaRoot(
        nodes=[
            NodeSchema(
                name="Tag",
                namespace="Test",
                description="Tag pointed at by an Attribute relationship (peer kept as-is on template).",
                include_in_menu=False,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
            NodeSchema(
                name="Interface",
                namespace="Test",
                description="Interface — child of Device via a Component relationship (peer rewritten).",
                include_in_menu=False,
                generate_template=True,
                attributes=[AttributeSchema(name="name", kind="Text")],
                relationships=[
                    RelationshipSchema(
                        name="device",
                        peer="TestDevice",
                        kind=RelationshipKind.PARENT,
                        cardinality=RelationshipCardinality.ONE,
                        optional=False,
                    ),
                ],
            ),
            NodeSchema(
                name="Device",
                namespace="Test",
                description="Device with a mix of Component, Attribute, and Parent relationships.",
                include_in_menu=False,
                generate_template=True,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
                relationships=[
                    RelationshipSchema(
                        name="interfaces",
                        peer="TestInterface",
                        kind=RelationshipKind.COMPONENT,
                        cardinality=RelationshipCardinality.MANY,
                        optional=True,
                    ),
                    RelationshipSchema(
                        name="tags",
                        peer="TestTag",
                        kind=RelationshipKind.ATTRIBUTE,
                        cardinality=RelationshipCardinality.MANY,
                        optional=True,
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def inherited_and_local_relationships_schema() -> SchemaRoot:
    """Node with `generate_template=True` that has both inherited and local relationships.

    The generic defines an ATTRIBUTE relationship (tags) and a GENERIC relationship
    (primary_site). The node inherits both and adds its own COMPONENT relationship
    (interfaces) and another ATTRIBUTE relationship (owner). Template and profile
    generation must handle the mixed provenance consistently across process() calls:
      - inherited rels get identifiers from the generic
      - local rels get auto-generated identifiers
      - template peer rewriting depends on rel.kind (COMPONENT rewrites, ATTRIBUTE keeps)
      - profile generation copies rels that pass support_profiles and aren't in constraints
    """
    return SchemaRoot(
        generics=[
            GenericSchema(
                name="NetworkElement",
                namespace="Test",
                description="Generic with relationships that will be inherited.",
                include_in_menu=False,
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                ],
                relationships=[
                    RelationshipSchema(
                        name="tags",
                        peer="TestTag",
                        kind=RelationshipKind.ATTRIBUTE,
                        cardinality=RelationshipCardinality.MANY,
                        optional=True,
                    ),
                    RelationshipSchema(
                        name="primary_site",
                        peer="TestSite",
                        kind=RelationshipKind.GENERIC,
                        cardinality=RelationshipCardinality.ONE,
                        optional=True,
                    ),
                ],
            ),
        ],
        nodes=[
            NodeSchema(
                name="Tag",
                namespace="Test",
                include_in_menu=False,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
            NodeSchema(
                name="Site",
                namespace="Test",
                include_in_menu=False,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
            NodeSchema(
                name="Person",
                namespace="Test",
                include_in_menu=False,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
            NodeSchema(
                name="Port",
                namespace="Test",
                include_in_menu=False,
                generate_template=True,
                attributes=[AttributeSchema(name="name", kind="Text")],
                relationships=[
                    RelationshipSchema(
                        name="router",
                        peer="TestRouter",
                        kind=RelationshipKind.PARENT,
                        cardinality=RelationshipCardinality.ONE,
                        optional=False,
                    ),
                ],
            ),
            NodeSchema(
                name="Router",
                namespace="Test",
                description="Node with inherited rels from generic + local rels.",
                include_in_menu=False,
                generate_template=True,
                inherit_from=["TestNetworkElement"],
                attributes=[
                    AttributeSchema(name="role", kind="Text", optional=True),
                ],
                relationships=[
                    # Local COMPONENT — template rewrites peer to TemplateTestPort
                    RelationshipSchema(
                        name="ports",
                        peer="TestPort",
                        kind=RelationshipKind.COMPONENT,
                        cardinality=RelationshipCardinality.MANY,
                        optional=True,
                    ),
                    # Local ATTRIBUTE — template keeps peer as-is
                    RelationshipSchema(
                        name="owner",
                        peer="TestPerson",
                        kind=RelationshipKind.ATTRIBUTE,
                        cardinality=RelationshipCardinality.ONE,
                        optional=True,
                    ),
                ],
            ),
        ],
    )


class TestSchemaProcessUniquenessIdempotent:
    """Loading the same schema payload twice must leave the persisted schema unchanged."""

    async def test_hfid_to_node_attr_to_template_propagation(
        self,
        register_core_models_schema: SchemaBranch,
        firewall_hfid_schema: SchemaRoot,
    ) -> None:
        """Calling SchemaBranch.process() repeatedly must not mutate the schema.

        SchemaBranch.process() can be called multiple times during a schema load, which will lead
        to unexpected schema drift if changes are made to the schema when calling process() on the
        same data multiple times.

        FirewallGenericDevice.name is implicitly unique because it is the only entry in the HFID;
        before the process_post_validation fix, the HFID-derived `unique` flag propagated to
        DcimFirewall.name one pass late, which eventually removed the attribute from the generated
        templates and profiles.
        """
        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=firewall_hfid_schema)

        _validate_process_idempotent(schema_branch)

    async def test_conflicting_inherit_unique_propagation(
        self,
        register_core_models_schema: SchemaBranch,
        conflicting_inherit_schema: SchemaRoot,
    ) -> None:
        """A node inheriting the same attribute from two generics with
        conflicting `unique` settings must still process idempotently.
        """
        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=conflicting_inherit_schema)

        _validate_process_idempotent(schema_branch)

    async def test_local_override_of_inherited_attribute(
        self,
        register_core_models_schema: SchemaBranch,
        local_override_inherited_schema: SchemaRoot,
    ) -> None:
        """Local attribute declaration wins over an inherited generic's attribute with the same name."""
        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=local_override_inherited_schema)

        _validate_process_idempotent(schema_branch)

    async def test_multi_generic_inheritance_conflicting_optional(
        self,
        register_core_models_schema: SchemaBranch,
        multi_generic_conflicting_optional_schema: SchemaRoot,
    ) -> None:
        """Multi-generic inheritance with conflicting non-unique fields must process idempotently."""
        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=multi_generic_conflicting_optional_schema)

        _validate_process_idempotent(schema_branch)

    async def test_read_only_attribute_excluded_from_template(
        self,
        register_core_models_schema: SchemaBranch,
        read_only_attribute_schema: SchemaRoot,
    ) -> None:
        """Read-only attribute is excluded from the generated template and stays excluded."""
        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=read_only_attribute_schema)

        _validate_process_idempotent(schema_branch)

    async def test_hfid_derivation_from_unique_attributes(
        self,
        register_core_models_schema: SchemaBranch,
        hfid_from_unique_attrs_schema: SchemaRoot,
    ) -> None:
        """HFID gets derived from `unique_attributes` when not explicitly provided."""
        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=hfid_from_unique_attrs_schema)

        _validate_process_idempotent(schema_branch)

    async def test_hfid_derivation_from_uniqueness_constraints(
        self,
        register_core_models_schema: SchemaBranch,
        hfid_from_constraints_schema: SchemaRoot,
    ) -> None:
        """HFID gets derived from a single-attr `uniqueness_constraints` when no HFID and no unique attrs."""
        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=hfid_from_constraints_schema)

        _validate_process_idempotent(schema_branch)

    async def test_profile_excludes_relationship_in_uniqueness_constraints(
        self,
        register_core_models_schema: SchemaBranch,
        profile_excludes_relationship_in_constraint_schema: SchemaRoot,
    ) -> None:
        """A relationship referenced in uniqueness_constraints (via HFID traversal) is excluded from profile."""
        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=profile_excludes_relationship_in_constraint_schema)

        _validate_process_idempotent(schema_branch)

    async def test_template_relationship_peer_resolution(
        self,
        register_core_models_schema: SchemaBranch,
        template_relationship_peer_resolution_schema: SchemaRoot,
    ) -> None:
        """Template relationship peers (rewritten vs kept) must be stable across process() calls."""
        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=template_relationship_peer_resolution_schema)

        _validate_process_idempotent(schema_branch)

    async def test_inherited_and_local_relationships(
        self,
        register_core_models_schema: SchemaBranch,
        inherited_and_local_relationships_schema: SchemaRoot,
    ) -> None:
        """Node with a mix of inherited and local relationships must process idempotently."""
        schema_branch = register_core_models_schema.duplicate()
        schema_branch.load_schema(schema=inherited_and_local_relationships_schema)

        _validate_process_idempotent(schema_branch)
