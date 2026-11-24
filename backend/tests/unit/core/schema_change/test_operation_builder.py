import json

import pytest
from pydantic import JsonValue

from infrahub.core.constants import HashableModelState
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.enums import SchemaOperationNodeType, SchemaOperationSection, SchemaOperationType
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder, SchemaOperationBuildResult
from infrahub.core.schema_change.operations import SchemaOperation
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import (
    EquivalenceCase,
    assert_same_load_result,
    base_generic_definition,
    base_node_definition,
    build_base_schema_root,
    build_direct_load_result,
    describe_operation,
    schema_element_id,
    validate_candidate_schema,
)

CONNECTOR_KIND = "TestingConnector"
CABLE_KIND = "TestingCable"
TICKET_KIND = "TestingTicket"

NEW_NODE_ID = "1f0a3d52-7c4b-4e2a-9b1d-000000000001"
NEW_NODE_ATTRIBUTE_ID = "1f0a3d52-7c4b-4e2a-9b1d-000000000002"
NEW_DEVICE_ATTRIBUTE_ID = "1f0a3d52-7c4b-4e2a-9b1d-000000000003"
NEW_NODE_NUMBER_POOL_ID = "1f0a3d52-7c4b-4e2a-9b1d-000000000004"
NEW_DEVICE_NUMBER_POOL_ID = "1f0a3d52-7c4b-4e2a-9b1d-000000000005"

OperationTarget = tuple[
    SchemaOperationType,
    str,
    SchemaOperationNodeType | None,
    SchemaOperationSection | None,
    str | None,
    str | None,
]


def _build(*, branch_schema: SchemaBranch, schema_root: SchemaRoot) -> SchemaOperationBuildResult:
    return SchemaOperationBuilder().build(
        branch_schema=branch_schema, schema_root=schema_root, default_branch_schema=branch_schema
    )


def _target(operation: SchemaOperation) -> OperationTarget:
    return (
        operation.operation_type,
        operation.kind,
        operation.node_type,
        operation.section,
        operation.element_name,
        operation.property_name,
    )


def _held_instance_values(value: JsonValue, location: str = "value") -> list[str]:
    """Return the location of every `id` or `number_pool_id` key with a value, at any depth."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"id", "number_pool_id"} and item is not None:
                found.append(f"{location}.{key}")
            found.extend(_held_instance_values(item, f"{location}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_held_instance_values(item, f"{location}[{index}]"))
    return found


def _add_attribute_to_generic(_: SchemaBranch) -> SchemaRoot:
    interface = base_generic_definition(TestKind.INTERFACE)
    interface.attributes.append(AttributeSchema(name="mtu", kind="Number", optional=True))
    return SchemaRoot(generics=[interface])


def _rename_attribute_on_generic(schema: SchemaBranch) -> SchemaRoot:
    interface = base_generic_definition(TestKind.INTERFACE)
    enabled = interface.get_attribute(name="enabled")
    enabled.id = schema_element_id(schema, TestKind.INTERFACE, "enabled")
    enabled.name = "admin_enabled"
    return SchemaRoot(generics=[interface])


def _file_with_every_operation_type(schema: SchemaBranch, *, reverse: bool) -> SchemaRoot:
    """Remove a kind and one of its attributes, add a generic and a node, and remove, add, change and rename attributes of other kinds."""
    tag = base_node_definition(TestKind.TAG)
    tag.state = HashableModelState.ABSENT
    tag.get_attribute(name="description").state = HashableModelState.ABSENT
    connector = GenericSchema(
        name="Connector",
        namespace="Testing",
        label="Connector",
        attributes=[AttributeSchema(name="gender", kind="Text", optional=True)],
    )
    cable = NodeSchema(
        name="Cable",
        namespace="Testing",
        label="Cable",
        inherit_from=[CONNECTOR_KIND],
        attributes=[AttributeSchema(name="length", kind="Number", optional=True)],
    )
    device = base_node_definition(TestKind.DEVICE)
    device.get_attribute(name="weight").state = HashableModelState.ABSENT
    device.attributes.append(AttributeSchema(name="serial", kind="Text", optional=True))
    device.get_attribute(name="manufacturer").label = "Maker"
    height = device.get_attribute(name="height")
    height.id = schema_element_id(schema, TestKind.DEVICE, "height")
    height.name = "rack_units"
    sfp = base_node_definition(TestKind.SFP)
    sfp.label = "Transceiver"

    nodes = [tag, cable, device, sfp]
    if reverse:
        nodes.reverse()
        device.attributes.reverse()
    return SchemaRoot(generics=[connector], nodes=nodes)


def _file_with_every_operation_type_in_order(schema: SchemaBranch) -> SchemaRoot:
    return _file_with_every_operation_type(schema, reverse=False)


def test_a_file_that_changes_nothing_gives_no_operation(equivalence_base_schema: SchemaBranch) -> None:
    result = _build(branch_schema=equivalence_base_schema, schema_root=build_base_schema_root())

    assert result.operations == []


def test_an_attribute_added_to_a_generic_gives_one_operation_on_the_generic_only(
    equivalence_base_schema: SchemaBranch,
) -> None:
    result = _build(
        branch_schema=equivalence_base_schema, schema_root=_add_attribute_to_generic(equivalence_base_schema)
    )

    assert [_target(operation) for operation in result.operations] == [
        (SchemaOperationType.ELEMENT_ADD, TestKind.INTERFACE, None, SchemaOperationSection.ATTRIBUTES, "mtu", None)
    ]
    added = result.operations[0].value
    assert isinstance(added, dict)
    assert (added["name"], added["kind"], added["optional"]) == ("mtu", "Number", True)


def test_turning_on_generate_profile_gives_no_operation_on_a_profile_kind(
    equivalence_base_schema: SchemaBranch,
) -> None:
    tag = base_node_definition(TestKind.TAG)
    tag.generate_profile = True

    result = _build(branch_schema=equivalence_base_schema, schema_root=SchemaRoot(nodes=[tag]))

    assert [describe_operation(operation) for operation in result.operations] == [
        describe_operation(
            SchemaOperation(
                operation_type=SchemaOperationType.NODE_PROPERTY,
                kind=TestKind.TAG,
                property_name="generate_profile",
                value=True,
                previous_value=False,
            )
        )
    ]


def test_a_unique_attribute_gives_no_operation_on_the_identifiers_that_processing_calculated(
    equivalence_base_schema: SchemaBranch,
) -> None:
    interface = base_generic_definition(TestKind.INTERFACE)
    interface.uniqueness_constraints = None
    interface.get_attribute(name="name").unique = True

    result = _build(branch_schema=equivalence_base_schema, schema_root=SchemaRoot(generics=[interface]))

    processed_interface = result.direct_load_schema.get(name=TestKind.INTERFACE, duplicate=False)
    assert processed_interface.human_friendly_id == ["name__value"]
    assert processed_interface.uniqueness_constraints == [["device", "name__value"], ["name__value"]]
    assert [describe_operation(operation) for operation in result.operations] == [
        describe_operation(
            SchemaOperation(
                operation_type=SchemaOperationType.ELEMENT_PROPERTY,
                kind=TestKind.INTERFACE,
                section=SchemaOperationSection.ATTRIBUTES,
                element_name="name",
                property_name="unique",
                value=True,
                previous_value=False,
            )
        )
    ]


def test_a_human_friendly_id_written_in_the_file_gives_an_operation(equivalence_base_schema: SchemaBranch) -> None:
    interface = base_generic_definition(TestKind.INTERFACE)
    interface.uniqueness_constraints = None
    interface.get_attribute(name="name").unique = True
    interface.human_friendly_id = ["name__value"]

    result = _build(branch_schema=equivalence_base_schema, schema_root=SchemaRoot(generics=[interface]))

    expected = [
        SchemaOperation(
            operation_type=SchemaOperationType.NODE_PROPERTY,
            kind=TestKind.INTERFACE,
            property_name="human_friendly_id",
            value=["name__value"],
            previous_value=None,
        ),
        SchemaOperation(
            operation_type=SchemaOperationType.ELEMENT_PROPERTY,
            kind=TestKind.INTERFACE,
            section=SchemaOperationSection.ATTRIBUTES,
            element_name="name",
            property_name="unique",
            value=True,
            previous_value=False,
        ),
    ]
    assert len(result.operations) == len(expected)
    assert {operation.property_name: describe_operation(operation) for operation in result.operations} == {
        operation.property_name: describe_operation(operation) for operation in expected
    }


def test_a_rename_by_id_names_the_element_by_its_name_before_the_load(equivalence_base_schema: SchemaBranch) -> None:
    device = base_node_definition(TestKind.DEVICE)
    weight = device.get_attribute(name="weight")
    weight.id = schema_element_id(equivalence_base_schema, TestKind.DEVICE, "weight")
    weight.name = "mass"

    result = _build(branch_schema=equivalence_base_schema, schema_root=SchemaRoot(nodes=[device]))

    assert [describe_operation(operation) for operation in result.operations] == [
        describe_operation(
            SchemaOperation(
                operation_type=SchemaOperationType.ELEMENT_PROPERTY,
                kind=TestKind.DEVICE,
                section=SchemaOperationSection.ATTRIBUTES,
                element_name="weight",
                property_name="name",
                value="mass",
                previous_value="weight",
            )
        )
    ]


def test_a_kind_renamed_in_its_name_and_its_namespace_gives_one_rename_operation(
    equivalence_base_schema: SchemaBranch,
) -> None:
    tag = base_node_definition(TestKind.TAG)
    tag.id = schema_element_id(equivalence_base_schema, TestKind.TAG)
    tag.name = "Sfp"
    tag.namespace = "Optics"

    result = _build(branch_schema=equivalence_base_schema, schema_root=SchemaRoot(nodes=[tag]))

    assert [describe_operation(operation) for operation in result.operations] == [
        describe_operation(
            SchemaOperation(
                operation_type=SchemaOperationType.NODE_RENAME,
                kind=TestKind.TAG,
                value={"name": "Sfp", "namespace": "Optics"},
                previous_value={"name": "Tag", "namespace": "Testing"},
            )
        )
    ]


def test_no_operation_holds_an_id_or_a_number_pool_id(equivalence_base_schema: SchemaBranch) -> None:
    ticket = NodeSchema(
        id=NEW_NODE_ID,
        name="Ticket",
        namespace="Testing",
        label="Ticket",
        attributes=[
            AttributeSchema(
                id=NEW_NODE_ATTRIBUTE_ID,
                name="number",
                kind="NumberPool",
                read_only=True,
                parameters={"start_range": 1, "end_range": 100, "number_pool_id": NEW_NODE_NUMBER_POOL_ID},
            )
        ],
    )
    device = base_node_definition(TestKind.DEVICE)
    device.attributes.append(
        AttributeSchema(
            id=NEW_DEVICE_ATTRIBUTE_ID,
            name="ticket_number",
            kind="NumberPool",
            read_only=True,
            parameters={"start_range": 1, "end_range": 50, "number_pool_id": NEW_DEVICE_NUMBER_POOL_ID},
        )
    )

    result = _build(branch_schema=equivalence_base_schema, schema_root=SchemaRoot(nodes=[ticket, device]))

    assert [_target(operation) for operation in result.operations] == [
        (
            SchemaOperationType.ELEMENT_ADD,
            TestKind.DEVICE,
            None,
            SchemaOperationSection.ATTRIBUTES,
            "ticket_number",
            None,
        ),
        (SchemaOperationType.NODE_ADD, TICKET_KIND, SchemaOperationNodeType.NODE, None, None, None),
    ]
    assert [_held_instance_values(operation.value) for operation in result.operations] == [[], []]
    dumped = json.dumps([operation.model_dump(mode="json", exclude_unset=True) for operation in result.operations])
    for instance_value in (
        NEW_NODE_ID,
        NEW_NODE_ATTRIBUTE_ID,
        NEW_DEVICE_ATTRIBUTE_ID,
        NEW_NODE_NUMBER_POOL_ID,
        NEW_DEVICE_NUMBER_POOL_ID,
    ):
        assert instance_value not in dumped


DIRECT_LOAD_SCHEMA_CASES: list[EquivalenceCase] = [
    EquivalenceCase(name="add_attribute_to_generic", schema_file=_add_attribute_to_generic),
    EquivalenceCase(name="rename_attribute_on_generic", schema_file=_rename_attribute_on_generic),
    EquivalenceCase(name="file_with_every_operation_type", schema_file=_file_with_every_operation_type_in_order),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in DIRECT_LOAD_SCHEMA_CASES])
def test_the_direct_load_schema_matches_a_direct_load(
    test_case: EquivalenceCase, equivalence_base_schema: SchemaBranch
) -> None:
    expected = build_direct_load_result(
        branch_schema=equivalence_base_schema,
        schema_root=test_case.schema_file(equivalence_base_schema),
        default_branch_schema=equivalence_base_schema,
    )

    result = _build(branch_schema=equivalence_base_schema, schema_root=test_case.schema_file(equivalence_base_schema))

    actual = validate_candidate_schema(
        branch_schema=equivalence_base_schema, candidate_schema=result.direct_load_schema
    )
    assert_same_load_result(expected=expected, actual=actual)


class TestOperationsOfAFileWithEveryOperationType:
    @pytest.fixture(scope="class")
    def build_result(self, equivalence_base_schema: SchemaBranch) -> SchemaOperationBuildResult:
        return _build(
            branch_schema=equivalence_base_schema,
            schema_root=_file_with_every_operation_type(equivalence_base_schema, reverse=False),
        )

    def test_operations_come_in_a_fixed_order_whatever_the_order_of_the_file(
        self, build_result: SchemaOperationBuildResult, equivalence_base_schema: SchemaBranch
    ) -> None:
        reversed_result = _build(
            branch_schema=equivalence_base_schema,
            schema_root=_file_with_every_operation_type(equivalence_base_schema, reverse=True),
        )

        expected: list[OperationTarget] = [
            (
                SchemaOperationType.ELEMENT_REMOVE,
                TestKind.TAG,
                None,
                SchemaOperationSection.ATTRIBUTES,
                "description",
                None,
            ),
            (SchemaOperationType.NODE_REMOVE, TestKind.TAG, None, None, None, None),
            (
                SchemaOperationType.ELEMENT_REMOVE,
                TestKind.DEVICE,
                None,
                SchemaOperationSection.ATTRIBUTES,
                "weight",
                None,
            ),
            (
                SchemaOperationType.ELEMENT_PROPERTY,
                TestKind.DEVICE,
                None,
                SchemaOperationSection.ATTRIBUTES,
                "manufacturer",
                "label",
            ),
            (
                SchemaOperationType.ELEMENT_PROPERTY,
                TestKind.DEVICE,
                None,
                SchemaOperationSection.ATTRIBUTES,
                "height",
                "name",
            ),
            (SchemaOperationType.ELEMENT_ADD, TestKind.DEVICE, None, SchemaOperationSection.ATTRIBUTES, "serial", None),
            (SchemaOperationType.NODE_PROPERTY, TestKind.SFP, None, None, None, "label"),
            (SchemaOperationType.NODE_ADD, CONNECTOR_KIND, SchemaOperationNodeType.GENERIC, None, None, None),
            (SchemaOperationType.NODE_ADD, CABLE_KIND, SchemaOperationNodeType.NODE, None, None, None),
        ]
        assert [_target(operation) for operation in build_result.operations] == expected
        assert [_target(operation) for operation in reversed_result.operations] == expected

    def test_operations_survive_a_json_round_trip(
        self, build_result: SchemaOperationBuildResult, equivalence_base_schema: SchemaBranch
    ) -> None:
        dumped = json.dumps(
            [operation.model_dump(mode="json", exclude_unset=True) for operation in build_result.operations]
        )
        loaded = [SchemaOperation.model_validate(item) for item in json.loads(dumped)]

        assert [describe_operation(operation) for operation in loaded] == [
            describe_operation(operation) for operation in build_result.operations
        ]
        applier = SchemaChangeApplier()
        from_built = applier.apply(
            target_schema=equivalence_base_schema,
            operations=build_result.operations,
            default_branch_schema=equivalence_base_schema,
        )
        from_loaded = applier.apply(
            target_schema=equivalence_base_schema, operations=loaded, default_branch_schema=equivalence_base_schema
        )
        assert from_loaded.get_hash() == from_built.get_hash()
        assert from_loaded.to_dict() == from_built.to_dict()
