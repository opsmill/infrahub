from infrahub.core.constants import (
    BranchSupportType,
    InfrahubKind,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind

from ...attribute_schema import AttributeSchema as Attr
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_check_definition = NodeSchema(
    name="CheckDefinition",
    namespace="Core",
    include_in_menu=False,
    icon="mdi:check-all",
    label="Check Definition",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.AWARE,
    uniqueness_constraints=[["name__value"]],
    generate_profile=False,
    inherit_from=[InfrahubKind.TASKTARGET],
    attributes=[
        Attr(name="name", kind="Text", unique=True),
        Attr(name="description", kind="Text", optional=True),
        Attr(name="file_path", kind="Text"),
        Attr(name="class_name", kind="Text"),
        Attr(name="timeout", kind="Number", default_value=10),
        Attr(name="parameters", kind="JSON", optional=True),
    ],
    relationships=[
        Rel(
            name="repository",
            peer=InfrahubKind.GENERICREPOSITORY,
            kind=RelKind.ATTRIBUTE,
            cardinality=Cardinality.ONE,
            identifier="check_definition__repository",
            optional=False,
        ),
        Rel(
            name="query",
            peer=InfrahubKind.GRAPHQLQUERY,
            kind=RelKind.ATTRIBUTE,
            identifier="check_definition__graphql_query",
            cardinality=Cardinality.ONE,
            optional=True,
        ),
        Rel(
            name="targets",
            peer=InfrahubKind.GENERICGROUP,
            kind=RelKind.ATTRIBUTE,
            identifier="check_definition___group",
            cardinality=Cardinality.ONE,
            optional=True,
        ),
        Rel(
            name="tags",
            peer=InfrahubKind.TAG,
            kind=RelKind.ATTRIBUTE,
            optional=True,
            cardinality=Cardinality.MANY,
        ),
    ],
)
