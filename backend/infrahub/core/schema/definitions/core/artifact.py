from infrahub.core.constants import (
    ArtifactStatus,
    BranchSupportType,
    ContentType,
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

core_artifact_target = GenericSchema(
    name="ArtifactTarget",
    include_in_menu=False,
    namespace="Core",
    description="Extend a node to be associated with artifacts",
    label="Artifact Target",
    relationships=[
        Rel(
            name="artifacts",
            peer=InfrahubKind.ARTIFACT,
            optional=True,
            cardinality=Cardinality.MANY,
            kind=RelKind.GENERIC,
            identifier="artifact__node",
        ),
    ],
)

core_artifact = NodeSchema(
    name="Artifact",
    namespace="Core",
    label="Artifact",
    include_in_menu=False,
    icon="mdi:file-document-outline",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.LOCAL,
    generate_profile=False,
    inherit_from=[InfrahubKind.TASKTARGET],
    documentation="/topics/artifact",
    attributes=[
        Attr(name="name", kind="Text"),
        Attr(
            name="status",
            kind="Text",
            enum=ArtifactStatus.available_types(),
        ),
        Attr(
            name="content_type",
            kind="Text",
            enum=ContentType.available_types(),
        ),
        Attr(
            name="checksum",
            kind="Text",
            optional=True,
        ),
        Attr(
            name="storage_id",
            kind="Text",
            optional=True,
            description="ID of the file in the object store",
        ),
        Attr(
            name="parameters",
            kind="JSON",
            optional=True,
        ),
    ],
    relationships=[
        Rel(
            name="object",
            peer=InfrahubKind.ARTIFACTTARGET,
            kind=RelKind.ATTRIBUTE,
            identifier="artifact__node",
            cardinality=Cardinality.ONE,
            optional=False,
        ),
        Rel(
            name="definition",
            peer=InfrahubKind.ARTIFACTDEFINITION,
            kind=RelKind.ATTRIBUTE,
            identifier="artifact__artifact_definition",
            cardinality=Cardinality.ONE,
            optional=False,
        ),
    ],
)

core_artifact_definition = NodeSchema(
    name="ArtifactDefinition",
    namespace="Core",
    include_in_menu=False,
    icon="mdi:file-document-multiple-outline",
    label="Artifact Definition",
    default_filter="name__value",
    order_by=["name__value"],
    display_labels=["name__value"],
    branch=BranchSupportType.AWARE,
    generate_profile=False,
    uniqueness_constraints=[["name__value"]],
    inherit_from=[InfrahubKind.TASKTARGET],
    documentation="/topics/artifact",
    attributes=[
        Attr(name="name", kind="Text", unique=True),
        Attr(name="artifact_name", kind="Text"),
        Attr(name="description", kind="Text", optional=True),
        Attr(name="parameters", kind="JSON"),
        Attr(name="content_type", kind="Text", enum=ContentType.available_types()),
    ],
    relationships=[
        Rel(
            name="targets",
            peer=InfrahubKind.GENERICGROUP,
            kind=RelKind.ATTRIBUTE,
            identifier="artifact_definition___group",
            cardinality=Cardinality.ONE,
            optional=False,
        ),
        Rel(
            name="transformation",
            peer=InfrahubKind.TRANSFORM,
            kind=RelKind.ATTRIBUTE,
            identifier="artifact_definition___transformation",
            cardinality=Cardinality.ONE,
            optional=False,
        ),
    ],
)
