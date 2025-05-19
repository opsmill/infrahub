from infrahub.actions.constants import BranchScope, NodeAction, ValueMatch
from infrahub.core.constants import AllowOverrideType, BranchSupportType, InfrahubKind
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind
from infrahub.core.schema.attribute_schema import AttributeSchema as Attr
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import (
    RelationshipSchema as Rel,
)

core_trigger_rule = GenericSchema(
    name="TriggerRule",
    namespace="Core",
    description="A rule that allows you to define a trigger and map it to an action that runs once the trigger condition is met.",
    include_in_menu=False,
    icon="mdi:filter-cog-outline",
    label="Trigger Rule",
    human_friendly_id=["name__value"],
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"]],
    generate_profile=False,
    attributes=[
        Attr(
            name="name",
            kind="Text",
            description="The name of the trigger rule",
            unique=True,
            order_weight=1000,
        ),
        Attr(
            name="description",
            kind="Text",
            description="A longer description to define the purpose of this trigger",
            optional=True,
            order_weight=2000,
        ),
        Attr(
            name="active",
            kind="Boolean",
            description="Indicates if this trigger is enabled or if it's just prepared, could be useful as you are setting up a trigger",
            optional=False,
            default_value=True,
            order_weight=2000,
        ),
        Attr(
            name="branch_scope",
            kind="Dropdown",
            description="Limits the scope with regards to what kind of branches to match against",
            choices=BranchScope.available_types(),
            default_value=BranchScope.DEFAULT_BRANCH.value.name,
            optional=False,
            order_weight=2000,
            allow_override=AllowOverrideType.NONE,
        ),
    ],
    relationships=[
        Rel(
            name="action",
            peer=InfrahubKind.ACTION,
            description="The action to execute once the trigger conditions has been met",
            identifier="core_action__core_triggerrule",
            kind=RelKind.ATTRIBUTE,
            cardinality=Cardinality.ONE,
            optional=False,
            order_weight=10000,
        ),
    ],
)

core_action = GenericSchema(
    name="Action",
    namespace="Core",
    description="An action that can be executed by a trigger",
    include_in_menu=False,
    icon="mdi:cards-diamond-outline",
    label="Core Action",
    human_friendly_id=["name__value"],
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"]],
    generate_profile=False,
    attributes=[
        Attr(
            name="name",
            description="Short descriptive name",
            kind="Text",
            unique=True,
            order_weight=1000,
        ),
        Attr(
            name="description",
            description="A detailed description of the action",
            kind="Text",
            optional=True,
            order_weight=2000,
        ),
    ],
    relationships=[
        Rel(
            name="triggers",
            description="The triggers that would execute this action once the triggering condition is met",
            peer=InfrahubKind.TRIGGERRULE,
            kind=RelKind.ATTRIBUTE,
            cardinality=Cardinality.MANY,
            identifier="core_action__core_triggerrule",
            optional=True,
            order_weight=10000,
        ),
    ],
)

core_node_trigger_match = GenericSchema(
    name="NodeTriggerMatch",
    namespace="Core",
    description="A trigger match condition related to changes to nodes within the Infrahub database",
    include_in_menu=False,
    icon="mdi:match",
    label="Node Trigger Match",
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=False,
    attributes=[],
    relationships=[
        Rel(
            name="trigger",
            peer="CoreNodeTriggerRule",
            description="The node trigger that this match is connected to",
            kind=RelKind.PARENT,
            cardinality=Cardinality.ONE,
            optional=False,
            identifier="core_node_trigger_match__core_trigger_rule",
            order_weight=10000,
        ),
    ],
)


core_generator_action = NodeSchema(
    name="GeneratorAction",
    namespace="Core",
    description="An action that runs a generator definition once triggered",
    include_in_menu=False,
    icon="mdi:cards-diamond-outline",
    label="Generator Action",
    human_friendly_id=["name__value"],
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"]],
    generate_profile=False,
    inherit_from=[InfrahubKind.ACTION],
    relationships=[
        Rel(
            name="generator",
            description="The generator definition to execute once this action gets triggered",
            peer=InfrahubKind.GENERATORDEFINITION,
            kind=RelKind.ATTRIBUTE,
            cardinality=Cardinality.ONE,
            identifier="core_generator_action__generator_definition",
            optional=False,
            order_weight=4000,
        ),
    ],
)

core_group_action = NodeSchema(
    name="GroupAction",
    namespace="Core",
    description="A group action that adds or removes members from a group once triggered",
    include_in_menu=False,
    icon="mdi:cards-diamond-outline",
    label="Group Action",
    human_friendly_id=["name__value"],
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"]],
    generate_profile=False,
    inherit_from=[InfrahubKind.ACTION],
    attributes=[
        Attr(
            name="add_members",
            kind="Boolean",
            description="Defines if the action should add or remove members from a group when triggered",
            unique=False,
            optional=False,
            default_value=True,
            order_weight=3000,
        ),
    ],
    relationships=[
        Rel(
            name="group",
            peer=InfrahubKind.GENERICGROUP,
            description="The target group of this action",
            kind=RelKind.ATTRIBUTE,
            cardinality=Cardinality.ONE,
            identifier="core_action__group",
            optional=False,
            order_weight=4000,
        ),
    ],
)


core_node_trigger_rule = NodeSchema(
    name="NodeTriggerRule",
    namespace="Core",
    description="A trigger rule that evaluates modifications to nodes within the Infrahub database",
    include_in_menu=False,
    icon="mdi:filter-cog-outline",
    label="Node Trigger Rule",
    human_friendly_id=["name__value"],
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"]],
    generate_profile=False,
    inherit_from=[InfrahubKind.TRIGGERRULE],
    attributes=[
        Attr(
            name="node_kind",
            kind="Text",
            description="The kind of node to match against",
            unique=False,
            optional=False,
            order_weight=3000,
        ),
        Attr(
            name="mutation_action",
            kind="Text",
            description="The type of modification to match against",
            enum=NodeAction.available_types(),
            unique=False,
            optional=False,
            order_weight=4000,
        ),
    ],
    relationships=[
        Rel(
            name="matches",
            peer="CoreNodeTriggerMatch",
            description="Use matches to configure the match condition for the selected node kind",
            kind=RelKind.COMPONENT,
            cardinality=Cardinality.MANY,
            optional=True,
            identifier="core_node_trigger_match__core_trigger_rule",
            order_weight=8000,
        ),
    ],
)

core_node_trigger_attribute_match = NodeSchema(
    name="NodeTriggerAttributeMatch",
    namespace="Core",
    description="A trigger match that matches against attribute changes on a node",
    include_in_menu=False,
    icon="mdi:match",
    label="Node Trigger Attribute Match",
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=False,
    inherit_from=["CoreNodeTriggerMatch"],
    attributes=[
        Attr(
            name="attribute_name",
            kind="Text",
            description="The attribue to match against",
            unique=False,
            optional=False,
            order_weight=1000,
        ),
        Attr(
            name="value",
            kind="Text",
            description="The value the attribute is updated to",
            unique=False,
            optional=True,
            order_weight=2000,
        ),
        Attr(
            name="value_previous",
            kind="Text",
            description="The previous value of the targeted attribute",
            unique=False,
            optional=True,
            order_weight=3000,
        ),
        Attr(
            name="value_match",
            kind="Dropdown",
            description="The value_match defines how the update will be evaluated, if it has to match the new value, the previous value or both",
            choices=ValueMatch.available_types(),
            default_value=ValueMatch.VALUE.value.name,
            optional=False,
            order_weight=5000,
        ),
    ],
    relationships=[],
)

core_node_trigger_relationship_match = NodeSchema(
    name="NodeTriggerRelationshipMatch",
    namespace="Core",
    description="A trigger match that matches against relationship changes on a node",
    include_in_menu=False,
    icon="mdi:match",
    label="Node Trigger Relationship Match",
    branch=BranchSupportType.AGNOSTIC,
    generate_profile=False,
    inherit_from=["CoreNodeTriggerMatch"],
    attributes=[
        Attr(
            name="relationship_name",
            kind="Text",
            description="The name of the relationship to match against",
            unique=False,
            optional=False,
            order_weight=1000,
        ),
        Attr(
            name="added",
            kind="Boolean",
            description="Indicates if the relationship was added or removed",
            unique=False,
            optional=False,
            default_value=True,
            order_weight=2000,
        ),
        Attr(
            name="peer",
            kind="Text",
            description="The node_id of the relationship peer to match against",
            unique=False,
            optional=True,
            order_weight=3000,
        ),
    ],
    relationships=[],
)


core_group_trigger_rule = NodeSchema(
    name="GroupTriggerRule",
    namespace="Core",
    description="A trigger rule that matches against updates to memberships within groups",
    include_in_menu=False,
    icon="mdi:filter-cog-outline",
    label="Group Trigger Rule",
    human_friendly_id=["name__value"],
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.AGNOSTIC,
    uniqueness_constraints=[["name__value"]],
    generate_profile=False,
    inherit_from=[InfrahubKind.TRIGGERRULE],
    attributes=[
        Attr(
            name="members_added",
            kind="Boolean",
            description="Indicate if the match should be for when members are added or removed",
            unique=False,
            optional=False,
            default_value=True,
            order_weight=3000,
        ),
    ],
    relationships=[
        Rel(
            name="group",
            peer=InfrahubKind.GENERICGROUP,
            description="The group to match against",
            kind=RelKind.ATTRIBUTE,
            cardinality=Cardinality.ONE,
            identifier="core_group_trigger__group",
            optional=False,
            order_weight=4000,
        ),
    ],
)
