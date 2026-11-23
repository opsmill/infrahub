from infrahub.core.constants import HashableModelState, InfrahubKind, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import (
    DEVICE_SPARE_SFPS_RELATIONSHIP,
    INTERFACE_KINDS,
    CaseScope,
    CombinedLoadCase,
)


def _add_relationship(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    virtual_interface = scope.node(TestKind.VIRTUAL_INTERFACE)
    virtual_interface.relationships.append(
        RelationshipSchema(
            name="parent_interface",
            peer=scope.kind(TestKind.PHYSICAL_INTERFACE),
            kind=RelationshipKind.GENERIC,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        )
    )
    return SchemaRoot(nodes=[virtual_interface])


def _remove_relationship(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    sfp = scope.node(TestKind.SFP)
    sfp.get_relationship(name="interface").state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[sfp])


def _rename_relationship(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    physical_interface = scope.node(TestKind.PHYSICAL_INTERFACE)
    sfp = physical_interface.get_relationship(name="sfp")
    sfp.id = scope.element_id(schema, TestKind.PHYSICAL_INTERFACE, "sfp")
    sfp.name = "transceiver"
    return SchemaRoot(nodes=[physical_interface])


def _change_relationship_peer(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    sfp = scope.node(TestKind.SFP)
    sfp.get_relationship(name="interface").peer = scope.kind(TestKind.INTERFACE)
    return SchemaRoot(nodes=[sfp])


def _change_relationship_cardinality(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    physical_interface = scope.node(TestKind.PHYSICAL_INTERFACE)
    physical_interface.get_relationship(name="sfp").cardinality = RelationshipCardinality.MANY
    return SchemaRoot(nodes=[physical_interface])


def _change_relationship_optional(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    device.get_relationship(name=DEVICE_SPARE_SFPS_RELATIONSHIP).optional = False
    return SchemaRoot(nodes=[device])


def _change_relationship_max_count(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    device.get_relationship(name=DEVICE_SPARE_SFPS_RELATIONSHIP).max_count = 4
    return SchemaRoot(nodes=[device])


def _change_relationship_kind(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    physical_interface = scope.node(TestKind.PHYSICAL_INTERFACE)
    physical_interface.get_relationship(name="sfp").kind = RelationshipKind.GENERIC
    return SchemaRoot(nodes=[physical_interface])


DEVICE_TAGS_RELATIONSHIP = "tags"


def _tags_relationship() -> RelationshipSchema:
    return RelationshipSchema(
        name=DEVICE_TAGS_RELATIONSHIP,
        peer=InfrahubKind.TAG,
        kind=RelationshipKind.GENERIC,
        cardinality=RelationshipCardinality.MANY,
        optional=True,
    )


def _base_with_device_tags(scope: CaseScope) -> SchemaRoot:
    base = scope.schema_root(INTERFACE_KINDS)
    device = next(node for node in base.nodes if node.kind == scope.kind(TestKind.DEVICE))
    device.relationships.append(_tags_relationship())
    return base


def _device_with_tags(scope: CaseScope, schema: SchemaBranch) -> NodeSchema:
    """Return the device of a case whose base has the tags relationship, with the IDs of its two relationships."""
    device = scope.node(TestKind.DEVICE)
    device.relationships.append(_tags_relationship())
    for name in (DEVICE_SPARE_SFPS_RELATIONSHIP, DEVICE_TAGS_RELATIONSHIP):
        device.get_relationship(name=name).id = scope.element_id(schema, TestKind.DEVICE, name)
    return device


def _rename_relationship_and_add_one_under_its_name(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    spare_sfps = device.get_relationship(name=DEVICE_SPARE_SFPS_RELATIONSHIP)
    spare_sfps.id = scope.element_id(schema, TestKind.DEVICE, DEVICE_SPARE_SFPS_RELATIONSHIP)
    spare_sfps.name = "reserve_sfps"
    new_spare_sfps = _tags_relationship()
    new_spare_sfps.name = DEVICE_SPARE_SFPS_RELATIONSHIP
    device.relationships.append(new_spare_sfps)
    return SchemaRoot(nodes=[device])


def _chain_relationship_renames(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    device = _device_with_tags(scope, schema)
    device.get_relationship(name=DEVICE_TAGS_RELATIONSHIP).name = "labels"
    device.get_relationship(name=DEVICE_SPARE_SFPS_RELATIONSHIP).name = DEVICE_TAGS_RELATIONSHIP
    return SchemaRoot(nodes=[device])


def _swap_relationship_names(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    device = _device_with_tags(scope, schema)
    spare_sfps = device.get_relationship(name=DEVICE_SPARE_SFPS_RELATIONSHIP)
    tags = device.get_relationship(name=DEVICE_TAGS_RELATIONSHIP)
    spare_sfps.name, tags.name = DEVICE_TAGS_RELATIONSHIP, DEVICE_SPARE_SFPS_RELATIONSHIP
    return SchemaRoot(nodes=[device])


PHYSICAL_INTERFACE_SFP_RELATIONSHIP = "sfp"
PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP = "spare_sfp"
PHYSICAL_INTERFACE_TYPE_ATTRIBUTE = "phys_type"
SFP_SERIAL_NUMBER_PATH = "serial_number__value"
PHYSICAL_INTERFACE_ORDER_BY = [
    f"{PHYSICAL_INTERFACE_SFP_RELATIONSHIP}__{SFP_SERIAL_NUMBER_PATH}",
    f"{PHYSICAL_INTERFACE_TYPE_ATTRIBUTE}__value",
]


def _spare_sfp_relationship(scope: CaseScope) -> RelationshipSchema:
    return RelationshipSchema(
        name=PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP,
        peer=scope.kind(TestKind.SFP),
        kind=RelationshipKind.GENERIC,
        cardinality=RelationshipCardinality.ONE,
        optional=True,
        identifier=f"{scope.namespace.lower()}__physicalinterface__spare_sfp",
    )


def _base_with_spare_sfp_and_order(scope: CaseScope) -> SchemaRoot:
    base = scope.schema_root(INTERFACE_KINDS)
    physical_interface = next(node for node in base.nodes if node.kind == scope.kind(TestKind.PHYSICAL_INTERFACE))
    physical_interface.relationships.append(_spare_sfp_relationship(scope))
    physical_interface.order_by = list(PHYSICAL_INTERFACE_ORDER_BY)
    return base


def _physical_interface_with_spare_sfp(scope: CaseScope, schema: SchemaBranch) -> NodeSchema:
    """Return the physical interface of a case whose base has the spare SFP and an order, with the IDs of its fields."""
    physical_interface = scope.node(TestKind.PHYSICAL_INTERFACE)
    physical_interface.relationships.append(_spare_sfp_relationship(scope))
    for name in (PHYSICAL_INTERFACE_SFP_RELATIONSHIP, PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP):
        physical_interface.get_relationship(name=name).id = scope.element_id(schema, TestKind.PHYSICAL_INTERFACE, name)
    physical_interface.get_attribute(name=PHYSICAL_INTERFACE_TYPE_ATTRIBUTE).id = scope.element_id(
        schema, TestKind.PHYSICAL_INTERFACE, PHYSICAL_INTERFACE_TYPE_ATTRIBUTE
    )
    return physical_interface


def _swap_sfp_relationship_names(physical_interface: NodeSchema) -> None:
    sfp = physical_interface.get_relationship(name=PHYSICAL_INTERFACE_SFP_RELATIONSHIP)
    spare_sfp = physical_interface.get_relationship(name=PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP)
    sfp.name, spare_sfp.name = PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP, PHYSICAL_INTERFACE_SFP_RELATIONSHIP


def _chain_relationship_renames_with_the_order_in_the_new_names(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    physical_interface = _physical_interface_with_spare_sfp(scope, schema)
    physical_interface.get_relationship(name=PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP).name = "backup_sfp"
    physical_interface.get_relationship(
        name=PHYSICAL_INTERFACE_SFP_RELATIONSHIP
    ).name = PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP
    physical_interface.order_by = [
        f"{PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP}__{SFP_SERIAL_NUMBER_PATH}",
        f"{PHYSICAL_INTERFACE_TYPE_ATTRIBUTE}__value",
    ]
    return SchemaRoot(nodes=[physical_interface])


def _swap_relationship_names_with_the_order_in_the_new_names(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    physical_interface = _physical_interface_with_spare_sfp(scope, schema)
    _swap_sfp_relationship_names(physical_interface)
    physical_interface.order_by = [
        f"{PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP}__{SFP_SERIAL_NUMBER_PATH}",
        f"{PHYSICAL_INTERFACE_TYPE_ATTRIBUTE}__value",
    ]
    return SchemaRoot(nodes=[physical_interface])


def _swap_relationship_names_with_the_order_unchanged(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    """State the order as it was, so that after the swap it orders by the other relationship."""
    physical_interface = _physical_interface_with_spare_sfp(scope, schema)
    _swap_sfp_relationship_names(physical_interface)
    physical_interface.order_by = list(PHYSICAL_INTERFACE_ORDER_BY)
    return SchemaRoot(nodes=[physical_interface])


def _swap_relationship_names_without_the_order(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    physical_interface = _physical_interface_with_spare_sfp(scope, schema)
    _swap_sfp_relationship_names(physical_interface)
    return SchemaRoot(nodes=[physical_interface])


def _rename_relationship_and_an_attribute_onto_its_name(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    physical_interface = _physical_interface_with_spare_sfp(scope, schema)
    physical_interface.get_relationship(name=PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP).name = "backup_sfp"
    physical_interface.get_attribute(
        name=PHYSICAL_INTERFACE_TYPE_ATTRIBUTE
    ).name = PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP
    physical_interface.order_by = [
        f"{PHYSICAL_INTERFACE_SFP_RELATIONSHIP}__{SFP_SERIAL_NUMBER_PATH}",
        f"{PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP}__value",
    ]
    return SchemaRoot(nodes=[physical_interface])


def _rename_attribute_and_a_relationship_onto_its_name(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    physical_interface = _physical_interface_with_spare_sfp(scope, schema)
    physical_interface.get_attribute(name=PHYSICAL_INTERFACE_TYPE_ATTRIBUTE).name = "port_type"
    physical_interface.get_relationship(
        name=PHYSICAL_INTERFACE_SPARE_SFP_RELATIONSHIP
    ).name = PHYSICAL_INTERFACE_TYPE_ATTRIBUTE
    physical_interface.order_by = [
        f"{PHYSICAL_INTERFACE_TYPE_ATTRIBUTE}__{SFP_SERIAL_NUMBER_PATH}",
        "port_type__value",
    ]
    return SchemaRoot(nodes=[physical_interface])


RELATIONSHIP_EQUIVALENCE_CASES: list[CombinedLoadCase] = [
    CombinedLoadCase(
        name="chain_relationship_renames_with_the_order_in_the_new_names",
        namespace="Relchainorder",
        base_kinds=INTERFACE_KINDS,
        schema_file=_chain_relationship_renames_with_the_order_in_the_new_names,
        base_file=_base_with_spare_sfp_and_order,
    ),
    CombinedLoadCase(
        name="swap_relationship_names_with_the_order_in_the_new_names",
        namespace="Relswaporder",
        base_kinds=INTERFACE_KINDS,
        schema_file=_swap_relationship_names_with_the_order_in_the_new_names,
        base_file=_base_with_spare_sfp_and_order,
    ),
    CombinedLoadCase(
        name="swap_relationship_names_with_the_order_unchanged",
        namespace="Relsameorder",
        base_kinds=INTERFACE_KINDS,
        schema_file=_swap_relationship_names_with_the_order_unchanged,
        base_file=_base_with_spare_sfp_and_order,
    ),
    CombinedLoadCase(
        name="swap_relationship_names_without_the_order",
        namespace="Relnoorder",
        base_kinds=INTERFACE_KINDS,
        schema_file=_swap_relationship_names_without_the_order,
        base_file=_base_with_spare_sfp_and_order,
    ),
    CombinedLoadCase(
        name="rename_relationship_and_an_attribute_onto_its_name",
        namespace="Relattrreuse",
        base_kinds=INTERFACE_KINDS,
        schema_file=_rename_relationship_and_an_attribute_onto_its_name,
        base_file=_base_with_spare_sfp_and_order,
    ),
    CombinedLoadCase(
        name="rename_attribute_and_a_relationship_onto_its_name",
        namespace="Attrrelreuse",
        base_kinds=INTERFACE_KINDS,
        schema_file=_rename_attribute_and_a_relationship_onto_its_name,
        base_file=_base_with_spare_sfp_and_order,
    ),
    CombinedLoadCase(
        name="rename_relationship_and_add_one_under_its_name",
        namespace="Relreuse",
        base_kinds=INTERFACE_KINDS,
        schema_file=_rename_relationship_and_add_one_under_its_name,
    ),
    CombinedLoadCase(
        name="chain_relationship_renames",
        namespace="Relchain",
        base_kinds=INTERFACE_KINDS,
        schema_file=_chain_relationship_renames,
        base_file=_base_with_device_tags,
    ),
    CombinedLoadCase(
        name="swap_relationship_names",
        namespace="Relswap",
        base_kinds=INTERFACE_KINDS,
        schema_file=_swap_relationship_names,
        base_file=_base_with_device_tags,
    ),
    CombinedLoadCase(
        name="add_relationship", namespace="Reladd", base_kinds=INTERFACE_KINDS, schema_file=_add_relationship
    ),
    CombinedLoadCase(
        name="remove_relationship",
        namespace="Relremove",
        base_kinds=INTERFACE_KINDS,
        schema_file=_remove_relationship,
    ),
    CombinedLoadCase(
        name="rename_relationship",
        namespace="Relrename",
        base_kinds=INTERFACE_KINDS,
        schema_file=_rename_relationship,
    ),
    CombinedLoadCase(
        name="change_relationship_peer",
        namespace="Relpeer",
        base_kinds=INTERFACE_KINDS,
        schema_file=_change_relationship_peer,
    ),
    CombinedLoadCase(
        name="change_relationship_cardinality",
        namespace="Relcardinality",
        base_kinds=INTERFACE_KINDS,
        schema_file=_change_relationship_cardinality,
    ),
    CombinedLoadCase(
        name="change_relationship_optional",
        namespace="Reloptional",
        base_kinds=INTERFACE_KINDS,
        schema_file=_change_relationship_optional,
    ),
    CombinedLoadCase(
        name="change_relationship_max_count",
        namespace="Relmaxcount",
        base_kinds=INTERFACE_KINDS,
        schema_file=_change_relationship_max_count,
    ),
    CombinedLoadCase(
        name="change_relationship_kind",
        namespace="Relkind",
        base_kinds=INTERFACE_KINDS,
        schema_file=_change_relationship_kind,
    ),
]
