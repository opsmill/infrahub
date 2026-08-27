from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.lock_utils import apply_payload_for_lock_names, get_lock_names_on_object_mutation
from infrahub.core.query.relationship import RelationshipGetPeerQuery
from tests.helpers.db_query_counter import CountingInfrahubDatabase

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


async def test_lock_names_do_not_depend_on_the_stored_peers(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch
) -> None:
    """Applying the payload for lock names gives the same names as hydrating the node first."""
    john = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await john.new(db=db, name="John", height=180)
    await john.save(db=db)

    jane = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await jane.new(db=db, name="Jane", height=170)
    await jane.save(db=db)

    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="accord", nbr_seats=5, owner=john.id, driver=john.id)
    await car.save(db=db)

    data = {"name": {"value": "civic"}, "owner": {"id": jane.id}}
    schema_branch = db.schema.get_schema_branch(name=default_branch.name)

    hydrated = await NodeManager.get_one_by_id_or_default_filter(
        db=db, kind="TestCar", id=car.id, branch=default_branch
    )
    await hydrated.from_graphql(db=db, data=data, process_pools=False)
    expected_lock_names = get_lock_names_on_object_mutation(node=hydrated, schema_branch=schema_branch)

    counting_db = CountingInfrahubDatabase.from_db(db=db)
    preview = await NodeManager.get_one_by_id_or_default_filter(
        db=counting_db, kind="TestCar", id=car.id, branch=default_branch
    )
    await apply_payload_for_lock_names(db=counting_db, node=preview, data=data)
    lock_names = get_lock_names_on_object_mutation(node=preview, schema_branch=schema_branch)

    assert counting_db.count_for(RelationshipGetPeerQuery.name) == 0
    assert lock_names == expected_lock_names
    assert lock_names == [
        # sha256 of the name the payload sets, which is the uniqueness constraint of TestCar
        "global.object.TestCar.bea359bea8f7d88ecff298e31876c7206ca36df3e5344293020ea745f9577378",
        f"relationship_count.testcar__testperson.{car.id}",
    ]
