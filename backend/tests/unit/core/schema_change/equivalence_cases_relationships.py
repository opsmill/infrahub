from infrahub.core.constants import HashableModelState, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import RelationshipSchema, SchemaRoot
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


def _change_relationship_kind(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    physical_interface = scope.node(TestKind.PHYSICAL_INTERFACE)
    physical_interface.get_relationship(name="sfp").kind = RelationshipKind.GENERIC
    return SchemaRoot(nodes=[physical_interface])


RELATIONSHIP_EQUIVALENCE_CASES: list[CombinedLoadCase] = [
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
        name="change_relationship_kind",
        namespace="Relkind",
        base_kinds=INTERFACE_KINDS,
        schema_file=_change_relationship_kind,
    ),
]
