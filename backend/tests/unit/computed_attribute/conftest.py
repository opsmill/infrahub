import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    RelationshipCardinality,
)
from infrahub.core.schema import (
    AttributeSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
)
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def car_person_schema_computed_attr(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema, data_schema
) -> None:
    SCHEMA = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Car",
                namespace="Test",
                attributes=[
                    AttributeSchema(
                        name="name",
                        kind="Text",
                        unique=True,
                    ),
                    AttributeSchema(
                        name="nbr_seats",
                        kind="Number",
                    ),
                    AttributeSchema(
                        name="computed_desc",
                        kind="Text",
                        read_only=True,
                        computed_attribute=ComputedAttribute(
                            kind=ComputedAttributeKind.JINJA2,
                            jinja2_template="{{ name__value }} has {{ nbr_seats__value }} seats",
                        ),
                    ),
                ],
                relationships=[
                    RelationshipSchema(
                        name="owner",
                        peer="TestPerson",
                        optional=False,
                        cardinality=RelationshipCardinality.ONE,
                    ),
                ],
            ),
            NodeSchema(
                name="Person",
                namespace="Test",
                attributes=[
                    AttributeSchema(
                        name="name",
                        kind="Text",
                        unique=True,
                    ),
                ],
                relationships=[
                    RelationshipSchema(
                        name="cars",
                        peer="TestCar",
                        cardinality=RelationshipCardinality.MANY,
                    ),
                ],
            ),
        ]
    )

    registry.schema.register_schema(schema=SCHEMA, branch=default_branch.name)
    default_branch.update_schema_hash()
    await default_branch.save(db=db)
