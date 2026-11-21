from infrahub.core.constants import HashableModelState, InfrahubKind, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.attribute_schema import NumberAttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import INTERFACE_KINDS, TAG_KINDS, CaseScope, CombinedLoadCase

MOVED_TAG_NAMESPACE = "Inventory"
RENAMED_PAST_EXISTING_KIND_NAMESPACE = "Optics"


def _add_attribute_to_generic(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    interface = scope.generic(TestKind.INTERFACE)
    # A parsed schema file holds the attribute class of the kind, which appending to the list does not convert to.
    interface.attributes.append(NumberAttributeSchema(name="mtu", kind="Number", optional=True))
    return SchemaRoot(generics=[interface])


def _turn_on_generate_profile(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    tag = scope.node(TestKind.TAG)
    tag.generate_profile = True
    return SchemaRoot(nodes=[tag])


def _turn_off_generate_template(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    device.generate_template = False
    return SchemaRoot(nodes=[device])


def _make_attribute_unique(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    device.get_attribute(name="part_number").unique = True
    return SchemaRoot(nodes=[device])


def _remove_attribute(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    device.get_attribute(name="weight").state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[device])


def _rename_attribute_on_node(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    weight = device.get_attribute(name="weight")
    weight.id = scope.element_id(schema, TestKind.DEVICE, "weight")
    weight.name = "mass"
    return SchemaRoot(nodes=[device])


def rename_attribute_on_generic(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    interface = scope.generic(TestKind.INTERFACE)
    enabled = interface.get_attribute(name="enabled")
    enabled.id = scope.element_id(schema, TestKind.INTERFACE, "enabled")
    enabled.name = "admin_enabled"
    return SchemaRoot(generics=[interface])


def _add_node(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    cable = NodeSchema(
        name="Cable",
        namespace=scope.namespace,
        label="Cable",
        human_friendly_id=["label__value"],
        attributes=[
            AttributeSchema(name="label", kind="Text", unique=True),
            AttributeSchema(name="length", kind="Number", optional=True),
        ],
        relationships=[
            RelationshipSchema(
                name="endpoints",
                peer=scope.kind(TestKind.PHYSICAL_INTERFACE),
                kind=RelationshipKind.GENERIC,
                cardinality=RelationshipCardinality.MANY,
                optional=True,
            )
        ],
    )
    return SchemaRoot(nodes=[cable])


def _rename_kind(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    tag = scope.node(TestKind.TAG)
    tag.id = scope.element_id(schema, TestKind.TAG)
    tag.name = "Label"
    return SchemaRoot(nodes=[tag])


def _change_kind_namespace(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    tag = scope.node(TestKind.TAG)
    tag.id = scope.element_id(schema, TestKind.TAG)
    tag.namespace = MOVED_TAG_NAMESPACE
    return SchemaRoot(nodes=[tag])


def _rename_kind_and_add_a_kind_under_its_name(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    tag = scope.node(TestKind.TAG)
    tag.id = scope.element_id(schema, TestKind.TAG)
    tag.name = "Label"
    new_tag = NodeSchema(
        name="Tag",
        namespace=scope.namespace,
        label="Tag",
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    )
    return SchemaRoot(nodes=[tag, new_tag])


def _rename_kind_and_namespace_past_an_existing_kind(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    """Give the tag the name of the case's SFP kind and move it to another namespace, which ends on a free kind."""
    tag = scope.node(TestKind.TAG)
    tag.id = scope.element_id(schema, TestKind.TAG)
    tag.name = "Sfp"
    tag.namespace = RENAMED_PAST_EXISTING_KIND_NAMESPACE
    return SchemaRoot(nodes=[tag])


def _add_generic_to_inherit_from(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    virtual_interface = scope.node(TestKind.VIRTUAL_INTERFACE)
    virtual_interface.inherit_from = [*virtual_interface.inherit_from, InfrahubKind.LINEAGESOURCE]
    return SchemaRoot(nodes=[virtual_interface])


def _remove_generic(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    interface_holder = scope.generic(TestKind.INTERFACE_HOLDER)
    interface_holder.state = HashableModelState.ABSENT
    interface = scope.generic(TestKind.INTERFACE)
    interface.get_relationship(name="device").peer = scope.kind(TestKind.DEVICE)
    device = scope.node(TestKind.DEVICE)
    device.inherit_from = []
    return SchemaRoot(generics=[interface_holder, interface], nodes=[device])


KIND_EQUIVALENCE_CASES: list[CombinedLoadCase] = [
    CombinedLoadCase(
        name="add_attribute_to_generic",
        namespace="Genericattradd",
        base_kinds=INTERFACE_KINDS,
        schema_file=_add_attribute_to_generic,
    ),
    CombinedLoadCase(
        name="turn_on_generate_profile",
        namespace="Tagprofile",
        base_kinds=TAG_KINDS,
        schema_file=_turn_on_generate_profile,
    ),
    CombinedLoadCase(
        name="turn_off_generate_template",
        namespace="Templateoff",
        base_kinds=INTERFACE_KINDS,
        schema_file=_turn_off_generate_template,
    ),
    CombinedLoadCase(
        name="make_attribute_unique",
        namespace="Uniqueon",
        base_kinds=INTERFACE_KINDS,
        schema_file=_make_attribute_unique,
    ),
    CombinedLoadCase(
        name="remove_attribute",
        namespace="Attrremove",
        base_kinds=INTERFACE_KINDS,
        schema_file=_remove_attribute,
    ),
    CombinedLoadCase(
        name="rename_attribute_on_node",
        namespace="Noderename",
        base_kinds=INTERFACE_KINDS,
        schema_file=_rename_attribute_on_node,
    ),
    CombinedLoadCase(
        name="rename_attribute_on_generic",
        namespace="Genericrename",
        base_kinds=INTERFACE_KINDS,
        schema_file=rename_attribute_on_generic,
    ),
    CombinedLoadCase(name="add_node", namespace="Nodeadd", base_kinds=INTERFACE_KINDS, schema_file=_add_node),
    CombinedLoadCase(name="rename_kind", namespace="Renamekind", base_kinds=TAG_KINDS, schema_file=_rename_kind),
    CombinedLoadCase(
        name="change_kind_namespace",
        namespace="Namespacemove",
        base_kinds=TAG_KINDS,
        schema_file=_change_kind_namespace,
    ),
    CombinedLoadCase(
        name="rename_kind_and_add_a_kind_under_its_name",
        namespace="Reusedkind",
        base_kinds=TAG_KINDS,
        schema_file=_rename_kind_and_add_a_kind_under_its_name,
    ),
    CombinedLoadCase(
        name="rename_kind_and_namespace_past_an_existing_kind",
        namespace="Pastexisting",
        base_kinds=(*INTERFACE_KINDS, TestKind.TAG),
        schema_file=_rename_kind_and_namespace_past_an_existing_kind,
    ),
    CombinedLoadCase(
        name="add_generic_to_inherit_from",
        namespace="Inheritadd",
        base_kinds=INTERFACE_KINDS,
        schema_file=_add_generic_to_inherit_from,
    ),
    CombinedLoadCase(
        name="remove_generic",
        namespace="Genericremove",
        base_kinds=INTERFACE_KINDS,
        schema_file=_remove_generic,
    ),
]
