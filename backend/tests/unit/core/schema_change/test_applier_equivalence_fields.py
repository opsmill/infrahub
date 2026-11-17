import pytest
from pydantic import JsonValue

from infrahub.core.constants import HashableModelState, InfrahubKind, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import (
    AttributeSchema,
    DropdownChoice,
    NodeExtensionSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaExtension,
    SchemaRoot,
)
from infrahub.core.schema.attribute_schema import TextAttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import (
    TAG_STATUS_ATTRIBUTE,
    EquivalenceCase,
    assert_same_load_result,
    base_generic_definition,
    base_node_definition,
    build_direct_load_result,
    schema_element_id,
    validate_candidate_schema,
)


def _add_dropdown_choice(_: SchemaBranch) -> SchemaRoot:
    tag = base_node_definition(TestKind.TAG)
    status = tag.get_attribute(name=TAG_STATUS_ATTRIBUTE)
    status.choices = [*(status.choices or []), DropdownChoice(name="planned", color="#1565c0")]
    return SchemaRoot(nodes=[tag])


def _remove_dropdown_choice(_: SchemaBranch) -> SchemaRoot:
    tag = base_node_definition(TestKind.TAG)
    for choice in tag.get_attribute(name=TAG_STATUS_ATTRIBUTE).choices or []:
        if choice.name == "reserved":
            choice.state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[tag])


def _change_dropdown_choice_color(_: SchemaBranch) -> SchemaRoot:
    tag = base_node_definition(TestKind.TAG)
    for choice in tag.get_attribute(name=TAG_STATUS_ATTRIBUTE).choices or []:
        if choice.name == "retired":
            choice.color = "#000000"
    return SchemaRoot(nodes=[tag])


def _absent_node(_: SchemaBranch) -> SchemaRoot:
    tag = base_node_definition(TestKind.TAG)
    tag.state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[tag])


def _absent_node_with_absent_attribute(_: SchemaBranch) -> SchemaRoot:
    tag = base_node_definition(TestKind.TAG)
    tag.state = HashableModelState.ABSENT
    tag.get_attribute(name="description").state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[tag])


def _absent_attribute_on_generic(_: SchemaBranch) -> SchemaRoot:
    interface = base_generic_definition(TestKind.INTERFACE)
    interface.get_attribute(name="enabled").state = HashableModelState.ABSENT
    return SchemaRoot(generics=[interface])


def _absent_relationship(_: SchemaBranch) -> SchemaRoot:
    physical_interface = base_node_definition(TestKind.PHYSICAL_INTERFACE)
    physical_interface.get_relationship(name="sfp").state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[physical_interface])


def _extend_node(_: SchemaBranch) -> SchemaRoot:
    extension = NodeExtensionSchema(
        kind=TestKind.DEVICE,
        # The applier builds the attribute class of the kind, where a load keeps the class an extension was parsed into.
        attributes=[TextAttributeSchema(name="serial", kind="Text", optional=True)],
        relationships=[
            RelationshipSchema(
                name="labels",
                peer=TestKind.TAG,
                kind=RelationshipKind.GENERIC,
                cardinality=RelationshipCardinality.MANY,
                optional=True,
            )
        ],
    )
    return SchemaRoot(extensions=SchemaExtension(nodes=[extension]))


def _replace_human_friendly_id(_: SchemaBranch) -> SchemaRoot:
    sfp = base_node_definition(TestKind.SFP)
    sfp.human_friendly_id = ["serial_number__value"]
    return SchemaRoot(nodes=[sfp])


def _replace_inherit_from(_: SchemaBranch) -> SchemaRoot:
    device = base_node_definition(TestKind.DEVICE)
    device.inherit_from = [InfrahubKind.LINEAGEOWNER]
    return SchemaRoot(nodes=[device])


def _replace_uniqueness_constraints(_: SchemaBranch) -> SchemaRoot:
    sfp = base_node_definition(TestKind.SFP)
    sfp.uniqueness_constraints = [["serial_number__value"]]
    return SchemaRoot(nodes=[sfp])


def _replace_order_by(_: SchemaBranch) -> SchemaRoot:
    tag = base_node_definition(TestKind.TAG)
    tag.order_by = ["description__value", "name__value"]
    return SchemaRoot(nodes=[tag])


def _replace_display_labels(_: SchemaBranch) -> SchemaRoot:
    device = base_node_definition(TestKind.DEVICE)
    device.display_labels = ["name__value", "manufacturer__value"]
    return SchemaRoot(nodes=[device])


def _change_attribute_kind(_: SchemaBranch) -> SchemaRoot:
    device = base_node_definition(TestKind.DEVICE)
    device.get_attribute(name="manufacturer").kind = "TextArea"
    return SchemaRoot(nodes=[device])


def _rename_attribute_and_write_human_friendly_id(schema: SchemaBranch) -> SchemaRoot:
    sfp = base_node_definition(TestKind.SFP)
    serial_number = sfp.get_attribute(name="serial_number")
    serial_number.id = schema_element_id(schema, TestKind.SFP, "serial_number")
    serial_number.name = "serial"
    sfp.human_friendly_id = ["phys_type__value", "serial__value"]
    sfp.uniqueness_constraints = None
    return SchemaRoot(nodes=[sfp])


def _clear_optional_text_field(_: SchemaBranch) -> SchemaRoot:
    device = base_node_definition(TestKind.DEVICE)
    device.default_filter = ""
    return SchemaRoot(nodes=[device])


FIELD_EQUIVALENCE_CASES: list[EquivalenceCase] = [
    EquivalenceCase(name="add_dropdown_choice", schema_file=_add_dropdown_choice),
    EquivalenceCase(name="remove_dropdown_choice", schema_file=_remove_dropdown_choice),
    EquivalenceCase(name="change_dropdown_choice_color", schema_file=_change_dropdown_choice_color),
    EquivalenceCase(name="absent_node", schema_file=_absent_node),
    EquivalenceCase(name="absent_node_with_absent_attribute", schema_file=_absent_node_with_absent_attribute),
    EquivalenceCase(name="absent_attribute_on_generic", schema_file=_absent_attribute_on_generic),
    EquivalenceCase(name="absent_relationship", schema_file=_absent_relationship),
    EquivalenceCase(name="extend_node_with_attribute_and_relationship", schema_file=_extend_node),
    EquivalenceCase(name="replace_human_friendly_id", schema_file=_replace_human_friendly_id),
    EquivalenceCase(name="replace_inherit_from", schema_file=_replace_inherit_from),
    EquivalenceCase(name="replace_uniqueness_constraints", schema_file=_replace_uniqueness_constraints),
    EquivalenceCase(name="replace_order_by", schema_file=_replace_order_by),
    EquivalenceCase(name="replace_display_labels", schema_file=_replace_display_labels),
    EquivalenceCase(name="change_attribute_kind", schema_file=_change_attribute_kind),
    EquivalenceCase(
        name="rename_attribute_and_write_human_friendly_id",
        schema_file=_rename_attribute_and_write_human_friendly_id,
    ),
    EquivalenceCase(name="clear_optional_text_field_with_empty_string", schema_file=_clear_optional_text_field),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in FIELD_EQUIVALENCE_CASES])
def test_applied_field_operations_give_the_direct_load_result(
    test_case: EquivalenceCase, equivalence_base_schema: SchemaBranch
) -> None:
    _assert_applied_operations_give_the_direct_load_result(test_case=test_case, branch_schema=equivalence_base_schema)


def _assert_applied_operations_give_the_direct_load_result(
    *, test_case: EquivalenceCase, branch_schema: SchemaBranch
) -> None:
    expected = build_direct_load_result(
        branch_schema=branch_schema,
        schema_root=test_case.schema_file(branch_schema),
        default_branch_schema=branch_schema,
    )
    assert expected.validation.diff.all, "the schema file of the case must change the schema"

    build_result = SchemaOperationBuilder().build(
        branch_schema=branch_schema,
        schema_root=test_case.schema_file(branch_schema),
        default_branch_schema=branch_schema,
    )
    applied_schema = SchemaChangeApplier().apply(
        target_schema=branch_schema,
        operations=build_result.operations,
        default_branch_schema=branch_schema,
    )
    actual = validate_candidate_schema(branch_schema=branch_schema, candidate_schema=applied_schema)

    assert_same_load_result(expected=expected, actual=actual)


COUNTER_KIND = "TestingCounter"
BOUNDS_POOL_ATTRIBUTE = "bounds_number"
RANGES_POOL_ATTRIBUTE = "ranges_number"
BOUNDS_POOL_PARAMETERS: dict[str, JsonValue] = {"start_range": 50, "end_range": 1200}
RANGES_POOL_PARAMETERS: dict[str, JsonValue] = {"ranges": [{"start": 1, "end": 10}, {"start": 100, "end": 200}]}


def _counter_definition(
    *,
    bounds_parameters: dict[str, JsonValue] = BOUNDS_POOL_PARAMETERS,
    ranges_parameters: dict[str, JsonValue] = RANGES_POOL_PARAMETERS,
) -> NodeSchema:
    return NodeSchema(
        name="Counter",
        namespace="Testing",
        label="Counter",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(
                name=BOUNDS_POOL_ATTRIBUTE, kind="NumberPool", read_only=True, parameters=bounds_parameters
            ),
            AttributeSchema(
                name=RANGES_POOL_ATTRIBUTE, kind="NumberPool", read_only=True, parameters=ranges_parameters
            ),
        ],
    )


def _replace_range_bounds_with_ranges(_: SchemaBranch) -> SchemaRoot:
    return SchemaRoot(
        nodes=[
            _counter_definition(bounds_parameters={"ranges": [{"start": 10, "end": 20}, {"start": 100, "end": 200}]})
        ]
    )


def _replace_ranges_with_range_bounds(_: SchemaBranch) -> SchemaRoot:
    return SchemaRoot(nodes=[_counter_definition(ranges_parameters={"start_range": 300, "end_range": 400})])


def _set_start_range_alone(_: SchemaBranch) -> SchemaRoot:
    return SchemaRoot(nodes=[_counter_definition(bounds_parameters={"start_range": 60})])


NUMBER_POOL_EQUIVALENCE_CASES: list[EquivalenceCase] = [
    EquivalenceCase(name="replace_number_pool_range_bounds_with_ranges", schema_file=_replace_range_bounds_with_ranges),
    EquivalenceCase(name="replace_number_pool_ranges_with_range_bounds", schema_file=_replace_ranges_with_range_bounds),
    EquivalenceCase(name="set_number_pool_start_range_alone", schema_file=_set_start_range_alone),
]


class TestNumberPoolParametersEquivalence:
    @pytest.fixture(scope="class")
    def counter_schema(self, equivalence_base_schema: SchemaBranch) -> SchemaBranch:
        """The shared schema with a node that holds one number pool declared by range bounds and one by ranges."""
        schema_root = SchemaRoot(nodes=[_counter_definition()])
        schema_root.generate_uuid()
        schema = equivalence_base_schema.duplicate()
        schema.load_schema(schema=schema_root)
        schema.process()
        return schema

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in NUMBER_POOL_EQUIVALENCE_CASES])
    def test_applied_number_pool_operations_give_the_direct_load_result(
        self, test_case: EquivalenceCase, counter_schema: SchemaBranch
    ) -> None:
        _assert_applied_operations_give_the_direct_load_result(test_case=test_case, branch_schema=counter_schema)


OVERRIDDEN_ATTRIBUTE = "enabled"


def _physical_interface_with_override(*, state: HashableModelState = HashableModelState.PRESENT) -> NodeSchema:
    physical_interface = base_node_definition(TestKind.PHYSICAL_INTERFACE)
    physical_interface.attributes.append(
        AttributeSchema(
            name=OVERRIDDEN_ATTRIBUTE,
            kind="Boolean",
            default_value=False,
            description="Disabled until cabled",
            order_weight=1033,
            state=state,
        )
    )
    return physical_interface


def _remove_override_of_inherited_attribute(_: SchemaBranch) -> SchemaRoot:
    return SchemaRoot(nodes=[_physical_interface_with_override(state=HashableModelState.ABSENT)])


class TestInheritedAttributeOverrideEquivalence:
    @pytest.fixture(scope="class")
    def override_schema(self, equivalence_base_schema: SchemaBranch) -> SchemaBranch:
        """The shared schema where a node overrides an attribute that it inherits from a generic."""
        schema_root = SchemaRoot(nodes=[_physical_interface_with_override()])
        schema_root.generate_uuid()
        schema = equivalence_base_schema.duplicate()
        schema.load_schema(schema=schema_root)
        schema.process()
        return schema

    def test_removed_override_gives_the_direct_load_result(self, override_schema: SchemaBranch) -> None:
        _assert_applied_operations_give_the_direct_load_result(
            test_case=EquivalenceCase(
                name="remove_override_of_inherited_attribute", schema_file=_remove_override_of_inherited_attribute
            ),
            branch_schema=override_schema,
        )
