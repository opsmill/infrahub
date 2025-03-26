from infrahub.core.constants import (
    BranchSupportType,
    GeneratorInstanceStatus,
    InfrahubKind,
)
from infrahub.core.constants import RelationshipCardinality as Cardinality
from infrahub.core.constants import RelationshipKind as RelKind

from ...attribute_schema import AttributeSchema as Attr
from ...node_schema import NodeSchema
from ...relationship_schema import (
    RelationshipSchema as Rel,
)

core_generator_definition = NodeSchema(
    name="GeneratorDefinition",
    namespace="Core",
    include_in_menu=False,
    icon="mdi:state-machine",
    label="Generator Definition",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.AWARE,
    uniqueness_constraints=[["name__value"]],
    generate_profile=False,
    inherit_from=[InfrahubKind.TASKTARGET],
    documentation="/topics/generator",
    attributes=[
        Attr(name="name", kind="Text", unique=True),
        Attr(name="description", kind="Text", optional=True),
        Attr(name="parameters", kind="JSON"),
        Attr(name="file_path", kind="Text"),
        Attr(name="class_name", kind="Text"),
        Attr(name="convert_query_response", kind="Boolean", optional=True, default_value=False),
    ],
    relationships=[
        Rel(
            name="query",
            peer=InfrahubKind.GRAPHQLQUERY,
            identifier="generator_definition__graphql_query",
            kind=RelKind.ATTRIBUTE,
            cardinality=Cardinality.ONE,
            optional=False,
        ),
        Rel(
            name="repository",
            peer=InfrahubKind.GENERICREPOSITORY,
            kind=RelKind.ATTRIBUTE,
            cardinality=Cardinality.ONE,
            identifier="generator_definition__repository",
            optional=False,
        ),
        Rel(
            name="targets",
            peer=InfrahubKind.GENERICGROUP,
            kind=RelKind.ATTRIBUTE,
            identifier="generator_definition___group",
            cardinality=Cardinality.ONE,
            optional=False,
        ),
    ],
)

core_generator_instance = NodeSchema(
    name="GeneratorInstance",
    namespace="Core",
    label="Generator Instance",
    include_in_menu=False,
    icon="mdi:file-document-outline",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.LOCAL,
    generate_profile=False,
    inherit_from=[InfrahubKind.TASKTARGET],
    documentation="/topics/generator",
    attributes=[
        Attr(name="name", kind="Text"),
        Attr(name="status", kind="Text", enum=GeneratorInstanceStatus.available_types()),
    ],
    relationships=[
        Rel(
            name="object",
            peer=InfrahubKind.NODE,
            kind=RelKind.ATTRIBUTE,
            identifier="generator__node",
            cardinality=Cardinality.ONE,
            optional=False,
        ),
        Rel(
            name="definition",
            peer=InfrahubKind.GENERATORDEFINITION,
            kind=RelKind.ATTRIBUTE,
            identifier="generator__generator_definition",
            cardinality=Cardinality.ONE,
            optional=False,
        ),
    ],
)
