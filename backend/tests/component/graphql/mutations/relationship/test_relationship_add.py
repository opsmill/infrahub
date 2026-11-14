from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.account import ObjectPermission
from infrahub.core.constants import InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.node import NodeListGetAttributeQuery, NodeListGetInfoQuery
from infrahub.core.query.relationship import RelationshipCreateQuery
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.graphql import graphql
from tests.helpers.permissions import define_permissions

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_relationship_add_reads_the_peers_once(
    db: InfrahubDatabase,
    default_permission_backend: None,
    default_branch: Branch,
    car_person_generics_data: dict[str, Node],
    session_first_account: AccountSession,
    first_account: Node,
) -> None:
    """The number of node reads does not grow with the number of peers the mutation adds."""
    await define_permissions(
        account=first_account,
        db=db,
        object_permissions=[
            ObjectPermission(
                namespace=namespace,
                name=name,
                action=PermissionAction.UPDATE.value,
                decision=PermissionDecision.ALLOW_ALL.value,
            )
            for namespace, name in (("Core", "StandardGroup"), ("Test", "ElectricCar"), ("Test", "GazCar"))
        ],
    )
    cars = [car_person_generics_data[name] for name in ("c1", "c2", "c3")]
    group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await group.new(db=db, name="group1")
    await group.save(db=db)

    counting_db = CountingInfrahubDatabase.from_db(db=db)
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(
        db=counting_db, branch=default_branch, account_session=session_first_account
    )
    result = await graphql(
        schema=gql_params.schema,
        source="""
        mutation ($id: String!, $nodes: [RelatedNodeInput]) {
            RelationshipAdd(data: {id: $id, name: "members", nodes: $nodes}) { ok }
        }
        """,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": group.id, "nodes": [{"id": car.id} for car in cars]},
    )

    assert result.errors is None
    assert {
        query.name: counting_db.count_for(query.name)
        for query in (NodeListGetInfoQuery, NodeListGetAttributeQuery, RelationshipCreateQuery)
    } == {
        # One read for the group and one read for all the peers.
        NodeListGetInfoQuery.name: 2,
        NodeListGetAttributeQuery.name: 2,
        RelationshipCreateQuery.name: 3,
    }
    saved_group = await NodeManager.get_one(db=db, id=group.id, branch=default_branch, raise_on_error=True)
    members = await saved_group.members.get_peers(db=db)  # type: ignore[attr-defined]
    assert set(members) == {car.id for car in cars}
