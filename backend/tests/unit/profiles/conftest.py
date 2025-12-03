import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, RelationshipCardinality, RelationshipKind
from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
)
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def profile_schema_with_attributes(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, data_schema, node_group_schema
) -> SchemaRoot:
    """Create a schema with a node that has attributes that can be set via profiles."""
    SCHEMA = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Device",
                namespace="Test",
                branch=BranchSupportType.AWARE.value,
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="description", kind="Text", optional=True),
                    AttributeSchema(name="status", kind="Text", optional=True),
                ],
            ),
        ]
    )

    registry.schema.register_schema(schema=SCHEMA, branch=default_branch.name)
    registry.schema.process_schema_branch(name=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)

    return SCHEMA


@pytest.fixture
async def profile_schema_with_generic_relationship(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, data_schema, node_group_schema
) -> SchemaRoot:
    """Create a schema with a node that has a generic relationship that can be set via profiles."""
    generic_schema = GenericSchema(
        name="GenericRole",
        namespace="Test",
        branch=BranchSupportType.AWARE.value,
        attributes=[AttributeSchema(name="role_name", kind="Text")],
    )

    role_schema = NodeSchema(
        name="Role",
        namespace="Test",
        branch=BranchSupportType.AWARE.value,
        inherit_from=["TestGenericRole"],
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    )

    device_schema = NodeSchema(
        name="Device",
        namespace="Test",
        branch=BranchSupportType.AWARE.value,
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="description", kind="Text", optional=True),
        ],
        relationships=[
            RelationshipSchema(
                name="role",
                peer="TestGenericRole",
                kind=RelationshipKind.GENERIC,
                optional=True,
                cardinality=RelationshipCardinality.ONE,
            ),
        ],
    )

    SCHEMA = SchemaRoot(nodes=[role_schema, device_schema], generics=[generic_schema])

    registry.schema.register_schema(schema=SCHEMA, branch=default_branch.name)
    registry.schema.process_schema_branch(name=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)

    return SCHEMA


@pytest.fixture
async def profile_schema_with_attribute_relationship(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema, data_schema, node_group_schema
) -> SchemaRoot:
    """Create a schema with a node that has an attribute relationship that can be set via profiles."""
    location_schema = NodeSchema(
        name="Location",
        namespace="Test",
        branch=BranchSupportType.AWARE.value,
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    )

    device_schema = NodeSchema(
        name="Device",
        namespace="Test",
        branch=BranchSupportType.AWARE.value,
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="description", kind="Text", optional=True),
        ],
        relationships=[
            RelationshipSchema(
                name="location",
                peer="TestLocation",
                kind=RelationshipKind.ATTRIBUTE,
                optional=True,
                cardinality=RelationshipCardinality.ONE,
            ),
        ],
    )

    SCHEMA = SchemaRoot(nodes=[location_schema, device_schema])

    registry.schema.register_schema(schema=SCHEMA, branch=default_branch.name)
    registry.schema.process_schema_branch(name=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)

    return SCHEMA
