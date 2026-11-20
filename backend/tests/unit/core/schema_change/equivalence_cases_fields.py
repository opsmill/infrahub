from infrahub.core.constants import HashableModelState, InfrahubKind, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import (
    AttributeSchema,
    DropdownChoice,
    GenericSchema,
    NodeExtensionSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaExtension,
    SchemaRoot,
)
from infrahub.core.schema.attribute_parameters import NumberAttributeParameters, TextAttributeParameters
from infrahub.core.schema.attribute_schema import NumberAttributeSchema, TextAttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.constants import TestKind
from tests.unit.core.schema_change.helpers import (
    COUNTER_KIND,
    INTERFACE_KINDS,
    TAG_KINDS,
    TAG_STATUS_ATTRIBUTE,
    CaseScope,
    CombinedLoadCase,
    counter_definition,
)


def _add_dropdown_choice(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    tag = scope.node(TestKind.TAG)
    status = tag.get_attribute(name=TAG_STATUS_ATTRIBUTE)
    status.choices = [*(status.choices or []), DropdownChoice(name="planned", color="#1565c0")]
    return SchemaRoot(nodes=[tag])


def _remove_dropdown_choice(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    tag = scope.node(TestKind.TAG)
    for choice in tag.get_attribute(name=TAG_STATUS_ATTRIBUTE).choices or []:
        if choice.name == "reserved":
            choice.state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[tag])


def _change_dropdown_choice_color(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    tag = scope.node(TestKind.TAG)
    for choice in tag.get_attribute(name=TAG_STATUS_ATTRIBUTE).choices or []:
        if choice.name == "retired":
            choice.color = "#000000"
    return SchemaRoot(nodes=[tag])


def _change_dropdown_choice_label(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    tag = scope.node(TestKind.TAG)
    for choice in tag.get_attribute(name=TAG_STATUS_ATTRIBUTE).choices or []:
        if choice.name == "retired":
            choice.label = "Decommissioned"
    return SchemaRoot(nodes=[tag])


def _remove_enum_value(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    airflow = device.get_attribute(name="airflow")
    airflow.enum = [value for value in airflow.enum or [] if value != "Mixed"]
    return SchemaRoot(nodes=[device])


MANUFACTURER_REGEX = r"^[A-Za-z ]+$"
INTERFACE_NAME_REGEX = r"^[a-z]+[0-9/]*$"


def _manufacturer_with_parameters(*, max_length: int) -> TextAttributeSchema:
    return TextAttributeSchema(
        name="manufacturer",
        kind="Text",
        parameters=TextAttributeParameters(regex=MANUFACTURER_REGEX, max_length=max_length),
    )


def _weight_with_parameters(*, max_value: int) -> NumberAttributeSchema:
    return NumberAttributeSchema(
        name="weight", kind="Number", parameters=NumberAttributeParameters(min_value=0, max_value=max_value)
    )


def _interface_name_with_regex(*, regex: str) -> TextAttributeSchema:
    return TextAttributeSchema(name="name", kind="Text", parameters=TextAttributeParameters(regex=regex))


def _device_with_attribute(scope: CaseScope, attribute: AttributeSchema) -> NodeSchema:
    device = scope.node(TestKind.DEVICE)
    device.attributes = [attribute if existing.name == attribute.name else existing for existing in device.attributes]
    return device


def _interface_with_attribute(scope: CaseScope, attribute: AttributeSchema) -> GenericSchema:
    interface = scope.generic(TestKind.INTERFACE)
    interface.attributes = [
        attribute if existing.name == attribute.name else existing for existing in interface.attributes
    ]
    return interface


def _base_with_device_attribute(scope: CaseScope, attribute: AttributeSchema) -> SchemaRoot:
    base_file = scope.schema_root(INTERFACE_KINDS)
    device = _device_with_attribute(scope, attribute)
    base_file.nodes = [device if node.kind == device.kind else node for node in base_file.nodes]
    return base_file


def _base_with_manufacturer_parameters(scope: CaseScope) -> SchemaRoot:
    return _base_with_device_attribute(scope, _manufacturer_with_parameters(max_length=40))


def _base_with_weight_parameters(scope: CaseScope) -> SchemaRoot:
    return _base_with_device_attribute(scope, _weight_with_parameters(max_value=100))


def _base_with_interface_name_regex(scope: CaseScope) -> SchemaRoot:
    base_file = scope.schema_root(INTERFACE_KINDS)
    interface = _interface_with_attribute(scope, _interface_name_with_regex(regex=INTERFACE_NAME_REGEX))
    base_file.generics = [interface if generic.kind == interface.kind else generic for generic in base_file.generics]
    return base_file


def _change_text_attribute_parameter(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    return SchemaRoot(nodes=[_device_with_attribute(scope, _manufacturer_with_parameters(max_length=64))])


def _change_number_attribute_parameter(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    return SchemaRoot(nodes=[_device_with_attribute(scope, _weight_with_parameters(max_value=500))])


def _change_attribute_parameter_on_generic(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    attribute = _interface_name_with_regex(regex=r"^[a-z]+[0-9/.]*$")
    return SchemaRoot(generics=[_interface_with_attribute(scope, attribute)])


def _change_attribute_parameter_through_extension(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    extension = NodeExtensionSchema(
        kind=scope.kind(TestKind.DEVICE),
        attributes=[
            TextAttributeSchema(name="manufacturer", kind="Text", parameters=TextAttributeParameters(max_length=64))
        ],
    )
    return SchemaRoot(extensions=SchemaExtension(nodes=[extension]))


def _change_number_pool_end_range(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    return SchemaRoot(
        nodes=[counter_definition(namespace=scope.namespace, bounds_parameters={"start_range": 50, "end_range": 2000})]
    )


def _absent_node(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    tag = scope.node(TestKind.TAG)
    tag.state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[tag])


def _absent_node_with_absent_attribute(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    tag = scope.node(TestKind.TAG)
    tag.state = HashableModelState.ABSENT
    tag.get_attribute(name="description").state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[tag])


def _absent_attribute_on_generic(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    interface = scope.generic(TestKind.INTERFACE)
    interface.get_attribute(name="enabled").state = HashableModelState.ABSENT
    return SchemaRoot(generics=[interface])


def _absent_relationship(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    physical_interface = scope.node(TestKind.PHYSICAL_INTERFACE)
    physical_interface.get_relationship(name="sfp").state = HashableModelState.ABSENT
    return SchemaRoot(nodes=[physical_interface])


def _extend_node(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    extension = NodeExtensionSchema(
        kind=scope.kind(TestKind.DEVICE),
        # The applier builds the attribute class of the kind, where a load keeps the class an extension was parsed into.
        attributes=[TextAttributeSchema(name="serial", kind="Text", optional=True)],
        relationships=[
            RelationshipSchema(
                name="labels",
                peer=scope.kind(TestKind.TAG),
                kind=RelationshipKind.GENERIC,
                cardinality=RelationshipCardinality.MANY,
                optional=True,
            )
        ],
    )
    return SchemaRoot(extensions=SchemaExtension(nodes=[extension]))


def _replace_human_friendly_id(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    sfp = scope.node(TestKind.SFP)
    sfp.human_friendly_id = ["serial_number__value"]
    return SchemaRoot(nodes=[sfp])


def _replace_inherit_from(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    device.inherit_from = [InfrahubKind.LINEAGEOWNER]
    return SchemaRoot(nodes=[device])


def _replace_uniqueness_constraints(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    sfp = scope.node(TestKind.SFP)
    sfp.uniqueness_constraints = [["serial_number__value"]]
    return SchemaRoot(nodes=[sfp])


def _replace_order_by(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    tag = scope.node(TestKind.TAG)
    tag.order_by = ["description__value", "name__value"]
    return SchemaRoot(nodes=[tag])


def _replace_display_labels(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    device.display_labels = ["name__value", "manufacturer__value"]
    return SchemaRoot(nodes=[device])


def _change_attribute_kind(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    device.get_attribute(name="manufacturer").kind = "TextArea"
    return SchemaRoot(nodes=[device])


def _rename_attribute_and_write_human_friendly_id(scope: CaseScope, schema: SchemaBranch) -> SchemaRoot:
    sfp = scope.node(TestKind.SFP)
    serial_number = sfp.get_attribute(name="serial_number")
    serial_number.id = scope.element_id(schema, TestKind.SFP, "serial_number")
    serial_number.name = "serial"
    sfp.human_friendly_id = ["phys_type__value", "serial__value"]
    sfp.uniqueness_constraints = None
    return SchemaRoot(nodes=[sfp])


def _clear_optional_text_field(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    device.default_filter = ""
    return SchemaRoot(nodes=[device])


def _replace_range_bounds_with_ranges(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    return SchemaRoot(
        nodes=[
            counter_definition(
                namespace=scope.namespace,
                bounds_parameters={"ranges": [{"start": 10, "end": 20}, {"start": 100, "end": 200}]},
            )
        ]
    )


def _replace_ranges_with_range_bounds(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    return SchemaRoot(
        nodes=[counter_definition(namespace=scope.namespace, ranges_parameters={"start_range": 300, "end_range": 400})]
    )


def _set_start_range_alone(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    return SchemaRoot(nodes=[counter_definition(namespace=scope.namespace, bounds_parameters={"start_range": 60})])


OVERRIDDEN_ATTRIBUTE = "enabled"


def _physical_interface_with_override(
    scope: CaseScope, *, state: HashableModelState = HashableModelState.PRESENT
) -> NodeSchema:
    physical_interface = scope.node(TestKind.PHYSICAL_INTERFACE)
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


def _base_with_override_of_inherited_attribute(scope: CaseScope) -> SchemaRoot:
    base_file = scope.schema_root(INTERFACE_KINDS)
    overriding_kind = scope.kind(TestKind.PHYSICAL_INTERFACE)
    base_file.nodes = [
        _physical_interface_with_override(scope) if node.kind == overriding_kind else node for node in base_file.nodes
    ]
    return base_file


def _remove_override_of_inherited_attribute(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    return SchemaRoot(nodes=[_physical_interface_with_override(scope, state=HashableModelState.ABSENT)])


FIELD_EQUIVALENCE_CASES: list[CombinedLoadCase] = [
    CombinedLoadCase(
        name="add_dropdown_choice",
        namespace="Choiceadd",
        base_kinds=TAG_KINDS,
        schema_file=_add_dropdown_choice,
    ),
    CombinedLoadCase(
        name="remove_dropdown_choice",
        namespace="Choiceremove",
        base_kinds=TAG_KINDS,
        schema_file=_remove_dropdown_choice,
    ),
    CombinedLoadCase(
        name="change_dropdown_choice_color",
        namespace="Choicecolor",
        base_kinds=TAG_KINDS,
        schema_file=_change_dropdown_choice_color,
    ),
    CombinedLoadCase(
        name="change_dropdown_choice_label",
        namespace="Choicelabel",
        base_kinds=TAG_KINDS,
        schema_file=_change_dropdown_choice_label,
    ),
    CombinedLoadCase(
        name="remove_enum_value",
        namespace="Enumremove",
        base_kinds=INTERFACE_KINDS,
        schema_file=_remove_enum_value,
    ),
    CombinedLoadCase(
        name="change_text_attribute_parameter",
        namespace="Textparam",
        base_kinds=INTERFACE_KINDS,
        schema_file=_change_text_attribute_parameter,
        base_file=_base_with_manufacturer_parameters,
    ),
    CombinedLoadCase(
        name="change_number_attribute_parameter",
        namespace="Numberparam",
        base_kinds=INTERFACE_KINDS,
        schema_file=_change_number_attribute_parameter,
        base_file=_base_with_weight_parameters,
    ),
    CombinedLoadCase(
        name="change_attribute_parameter_on_generic",
        namespace="Genericparam",
        base_kinds=INTERFACE_KINDS,
        schema_file=_change_attribute_parameter_on_generic,
        base_file=_base_with_interface_name_regex,
    ),
    CombinedLoadCase(
        name="change_attribute_parameter_through_extension",
        namespace="Extensionparam",
        base_kinds=INTERFACE_KINDS,
        schema_file=_change_attribute_parameter_through_extension,
        base_file=_base_with_manufacturer_parameters,
    ),
    CombinedLoadCase(
        name="change_number_pool_end_range",
        namespace="Poolend",
        base_kinds=(COUNTER_KIND,),
        schema_file=_change_number_pool_end_range,
    ),
    CombinedLoadCase(name="absent_node", namespace="Nodeabsent", base_kinds=TAG_KINDS, schema_file=_absent_node),
    CombinedLoadCase(
        name="absent_node_with_absent_attribute",
        namespace="Nodeattrabsent",
        base_kinds=TAG_KINDS,
        schema_file=_absent_node_with_absent_attribute,
    ),
    CombinedLoadCase(
        name="absent_attribute_on_generic",
        namespace="Genericabsent",
        base_kinds=INTERFACE_KINDS,
        schema_file=_absent_attribute_on_generic,
    ),
    CombinedLoadCase(
        name="absent_relationship",
        namespace="Relabsent",
        base_kinds=INTERFACE_KINDS,
        schema_file=_absent_relationship,
    ),
    CombinedLoadCase(
        name="extend_node_with_attribute_and_relationship",
        namespace="Nodeextend",
        base_kinds=(*INTERFACE_KINDS, *TAG_KINDS),
        schema_file=_extend_node,
    ),
    CombinedLoadCase(
        name="replace_human_friendly_id",
        namespace="Hfidreplace",
        base_kinds=INTERFACE_KINDS,
        schema_file=_replace_human_friendly_id,
    ),
    CombinedLoadCase(
        name="replace_inherit_from",
        namespace="Inheritreplace",
        base_kinds=INTERFACE_KINDS,
        schema_file=_replace_inherit_from,
    ),
    CombinedLoadCase(
        name="replace_uniqueness_constraints",
        namespace="Uniquereplace",
        base_kinds=INTERFACE_KINDS,
        schema_file=_replace_uniqueness_constraints,
    ),
    CombinedLoadCase(
        name="replace_order_by",
        namespace="Orderreplace",
        base_kinds=TAG_KINDS,
        schema_file=_replace_order_by,
    ),
    CombinedLoadCase(
        name="replace_display_labels",
        namespace="Labelsreplace",
        base_kinds=INTERFACE_KINDS,
        schema_file=_replace_display_labels,
    ),
    CombinedLoadCase(
        name="change_attribute_kind",
        namespace="Attrkind",
        base_kinds=INTERFACE_KINDS,
        schema_file=_change_attribute_kind,
    ),
    CombinedLoadCase(
        name="rename_attribute_and_write_human_friendly_id",
        namespace="Hfidrename",
        base_kinds=INTERFACE_KINDS,
        schema_file=_rename_attribute_and_write_human_friendly_id,
    ),
    CombinedLoadCase(
        name="clear_optional_text_field_with_empty_string",
        namespace="Textclear",
        base_kinds=INTERFACE_KINDS,
        schema_file=_clear_optional_text_field,
    ),
    CombinedLoadCase(
        name="replace_number_pool_range_bounds_with_ranges",
        namespace="Poolbounds",
        base_kinds=(COUNTER_KIND,),
        schema_file=_replace_range_bounds_with_ranges,
    ),
    CombinedLoadCase(
        name="replace_number_pool_ranges_with_range_bounds",
        namespace="Poolranges",
        base_kinds=(COUNTER_KIND,),
        schema_file=_replace_ranges_with_range_bounds,
    ),
    CombinedLoadCase(
        name="set_number_pool_start_range_alone",
        namespace="Poolstart",
        base_kinds=(COUNTER_KIND,),
        schema_file=_set_start_range_alone,
    ),
    CombinedLoadCase(
        name="remove_override_of_inherited_attribute",
        namespace="Overrideremove",
        base_kinds=INTERFACE_KINDS,
        schema_file=_remove_override_of_inherited_attribute,
        base_file=_base_with_override_of_inherited_attribute,
    ),
]
