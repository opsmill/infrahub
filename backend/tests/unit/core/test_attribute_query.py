from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.query.attribute import AttributeGetQuery
from infrahub.database import InfrahubDatabase


async def test_AttributeGetQuery(db: InfrahubDatabase, default_branch: Branch, car_person_schema):
    obj = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await obj.new(db=db, name="John", height=180)
    await obj.save(db=db)

    query = await AttributeGetQuery.init(db=db, attr=obj.name)
    await query.execute(db=db)

    assert query.num_of_results == 3
