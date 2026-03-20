import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    InfrahubKind,
    RelationshipCardinality,
)
from infrahub.core.node import Node
from infrahub.core.schema import (
    AttributeSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
)
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


@pytest.fixture
async def gqlquery01(db: InfrahubDatabase, register_core_models_schema: SchemaBranch, default_branch: Branch) -> Node:
    query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY, branch=default_branch)
    await query.new(
        db=db, name="query01", query="query { TestCar { name { value } } }", models=["TestCar", "TestPerson"]
    )
    await query.save(db=db)
    return query


@pytest.fixture
async def repo01(
    db: InfrahubDatabase, register_core_models_schema: SchemaBranch, default_branch: Branch, gqlquery01: Node
) -> Node:
    repo = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
    repo = await repo.new(
        db=db, name="repo02", ref=default_branch.name, commit="commit02", location="location02", queries=[gqlquery01]
    )
    await repo.save(db=db)
    return repo


@pytest.fixture
async def transform01(
    db: InfrahubDatabase,
    register_core_models_schema: SchemaBranch,
    default_branch: Branch,
    gqlquery01: Node,
    repo01: Node,
) -> Node:
    transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON, branch=default_branch)
    await transform.new(
        db=db, name="transform01", file_path="transform.py", class_name="Transform", query=gqlquery01, repository=repo01
    )
    await transform.save(db=db)
    return transform


@pytest.fixture
async def car_person_schema_computed_attr(
    db: InfrahubDatabase, default_branch: Branch, node_group_schema: None, data_schema: None
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
                    AttributeSchema(
                        name="computed_desc_python",
                        kind="Text",
                        read_only=True,
                        optional=True,
                        computed_attribute=ComputedAttribute(
                            kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                            transform="transform01",
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
