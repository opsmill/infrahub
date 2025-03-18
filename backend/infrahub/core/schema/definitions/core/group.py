from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind

from ...attribute_schema import AttributeSchema as Attr
from ...generic_schema import GenericSchema
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_group = GenericSchema(
    name="Group",
    namespace="Core",
    description="Generic Group Object.",
    label="Group",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["label__value"],
    include_in_menu=False,
    icon="mdi:group",
    hierarchical=True,
    branch=BranchSupportType.AWARE,
    uniqueness_constraints=[["name__value"]],
    attributes=[
        Attr(name="name", kind="Text", unique=True),
        Attr(name="label", kind="Text", optional=True),
        Attr(name="description", kind="Text", optional=True),
        Attr(name="group_type", kind="Text", enum=["default", "internal"], default_value="default", optional=False),
    ],
    relationships=[
        Rel(
            name="members",
            peer=InfrahubKind.NODE,
            optional=True,
            identifier="group_member",
            cardinality=Cardinality.MANY,
            branch=BranchSupportType.AWARE,
        ),
        Rel(
            name="subscribers",
            peer=InfrahubKind.NODE,
            optional=True,
            identifier="group_subscriber",
            cardinality=Cardinality.MANY,
        ),
    ],
)

core_standard_group = NodeSchema(
    name="StandardGroup",
    namespace="Core",
    description="Group of nodes of any kind.",
    include_in_menu=False,
    icon="mdi:account-group",
    label="Standard Group",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.AWARE,
    inherit_from=[InfrahubKind.GENERICGROUP],
    generate_profile=False,
)

core_generator_group = NodeSchema(
    name="GeneratorGroup",
    namespace="Core",
    description="Group of nodes that are created by a generator.",
    include_in_menu=False,
    icon="mdi:state-machine",
    label="Generator Group",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.LOCAL,
    inherit_from=[InfrahubKind.GENERICGROUP],
    generate_profile=False,
)

core_graphql_query_group = NodeSchema(
    name="GraphQLQueryGroup",
    namespace="Core",
    description="Group of nodes associated with a given GraphQLQuery.",
    include_in_menu=False,
    icon="mdi:account-group",
    label="GraphQL Query Group",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.LOCAL,
    inherit_from=[InfrahubKind.GENERICGROUP],
    generate_profile=False,
    attributes=[
        Attr(name="parameters", kind="JSON", optional=True),
    ],
    relationships=[
        Rel(
            name="query",
            peer=InfrahubKind.GRAPHQLQUERY,
            optional=False,
            cardinality=Cardinality.ONE,
            kind=RelKind.ATTRIBUTE,
        ),
    ],
)
