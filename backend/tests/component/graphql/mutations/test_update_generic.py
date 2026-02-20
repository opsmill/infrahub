from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql


async def test_display_label_generic(db: InfrahubDatabase, animal_person_schema: SchemaRoot, branch: Branch) -> None:
    person_schema = animal_person_schema.get(name="TestPerson")
    dog_schema = animal_person_schema.get(name="TestDog")
    cat_schema = animal_person_schema.get(name="TestCat")

    person1 = await Node.init(db=db, schema=person_schema, branch=branch)
    await person1.new(db=db, name="Jack")
    await person1.save(db=db)

    dog1 = await Node.init(db=db, schema=dog_schema, branch=branch)
    await dog1.new(db=db, name="Rocky", breed="Labrador", owner=person1)
    await dog1.save(db=db)

    cat1 = await Node.init(db=db, schema=cat_schema, branch=branch)
    await cat1.new(db=db, name="Kitty", breed="Persian", owner=person1)
    await cat1.save(db=db)

    query = """
    mutation ($id: String!){
        TestAnimalUpdate(data: {id: $id, weight: { value: 15 }}) {
            ok
            object {
                id
                weight {
                    value
                }
            }
        }
    }
    """
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": dog1.id},
    )

    assert result.errors is None
    assert result.data
    assert result.data["TestAnimalUpdate"]["ok"] is True
    assert result.data["TestAnimalUpdate"]["object"]["weight"]["value"]
