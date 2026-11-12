from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


async def test_create_check_unique(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "Violates uniqueness constraint" in result.errors[0].message


async def test_create_check_unique_across_branch(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """

    branch1 = await create_branch(branch_name="branch1", db=db)

    branch1.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch1)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "Violates uniqueness constraint" in result.errors[0].message


async def test_create_check_unique_in_branch(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    branch1 = await create_branch(branch_name="branch1", db=db)

    p1 = await Node.init(db=db, schema="TestPerson", branch=branch1)
    await p1.new(db=db, name="John", height=180)
    await p1.save(db=db)

    query = """
    mutation {
        TestPersonCreate(data: {name: { value: "John"}, height: {value: 182}}) {
            ok
            object {
                id
            }
        }
    }
    """
    branch1.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch1)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors
    assert len(result.errors) == 1
    assert "Violates uniqueness constraint" in result.errors[0].message


async def test_attr_optional_uniqueness_constraint_create(
    db: InfrahubDatabase, default_branch: Branch, optional_attr_uniqueness_constraint_schema: NodeSchema
) -> None:
    query = """
    mutation {
        TestAttrOptionalUniquenessSchemaCreate(
            data: {
                description: { value: "the name is null" }
            }
        ){
            ok
            object {
                id
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    assert result.errors is None

    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert result.errors[0].message == "Violates uniqueness constraint 'name-description'"


async def test_create_with_uniqueness_constraint_violation(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    car_schema = schema_branch.get("TestCar", duplicate=True)
    car_schema.uniqueness_constraints = [["owner", "color"]]
    schema_branch.set(name="TestCar", schema=car_schema)

    p1 = await Node.init(db=db, schema="TestPerson")
    await p1.new(db=db, name="Bruce Wayne", height=180)
    await p1.save(db=db)
    c1 = await Node.init(db=db, schema="TestCar")
    await c1.new(db=db, name="Batmobile", is_electric=False, nbr_seats=3, color="#123456", owner=p1)
    await c1.save(db=db)

    query = """
    mutation {
        TestCarCreate(data: {
            name: { value: "Batcycle" },
            nbr_seats: { value: 1 },
            color: { value: "#123456" },
            is_electric: { value: true },
            owner: { id: "Bruce Wayne" },
        }) {
            ok
            object {
                id
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors
    assert len(result.errors) == 1
    assert "Violates uniqueness constraint 'owner-color'" in result.errors[0].message
