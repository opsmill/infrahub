from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from tests.conftest import do_car_person_schema_unregistered
from tests.helpers.ownership import add_node, create, create_groups, from_node, own, read_node, run

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

GROUP_NAMES = ("server-team", "network-team", "security-team")

OWNERSHIP = "ownership { state origin origin_node { id } owners { id } }"

CREATE_CAR = """
mutation($name: String!, $person: String!, $owners: [MetadataNodeInput!], $color: TextAttributeCreate) {
    TestCarCreate(data: {name: {value: $name}, owner: {id: $person}, color: $color, node_metadata: {owners: $owners}}) {
        object { id }
    }
}
"""

UPDATE_COLOR = """
mutation($id: String!, $color: TextAttributeUpdate) {
    TestCarUpdate(data: {id: $id, color: $color}) { ok }
}
"""

READ_COLOR = """
query($ids: [ID]) {
    TestCar(ids: $ids) { edges { node { color { value owner { id } %(ownership)s } } } }
}
""" % {"ownership": OWNERSHIP}

CREATE_CAR_WITH_LINK_OWNER = """
mutation($name: String!, $person: String!, $link_owner: String!) {
    TestCarCreate(data: {name: {value: $name}, owner: {id: $person, _relation__owner: $link_owner}}) {
        object { id }
    }
}
"""

SET_LINK_OWNER = """
mutation($id: String!, $person: String!, $link_owner: String!) {
    TestCarUpdate(data: {id: $id, owner: {id: $person, _relation__owner: $link_owner}}) { ok }
}
"""

SET_CARS_OWNERS = """
mutation($id: String!, $owners: [MetadataNodeInput!]) {
    TestPersonUpdate(data: {id: $id, node_metadata: {field_owners: [{field: "cars", owners: $owners}]}}) { ok }
}
"""

READ_CARS = """
query($ids: [ID]) {
    TestPerson(ids: $ids) {
        edges { node { cars { count %(ownership)s edges { %(ownership)s properties { owner { id } } node { id } } } } }
    }
}
""" % {"ownership": OWNERSHIP}


@dataclass
class OwnerWriteTestCase:
    name: str
    own_owners: tuple[str, ...] | None
    """The own owners of the color before the writes: None to inherit, an empty tuple for "no owner"."""
    owner: str | None
    """The group that the deprecated `owner` field returns before the writes."""


OWNER_WRITE_TEST_CASES: list[OwnerWriteTestCase] = [
    OwnerWriteTestCase(name="inherits_the_owners_of_the_car", own_owners=None, owner=None),
    OwnerWriteTestCase(name="has_no_owner", own_owners=(), owner=None),
    OwnerWriteTestCase(name="has_one_own_owner", own_owners=("network-team",), owner="network-team"),
]


class TestDeprecatedOwnerField:
    @pytest.fixture(scope="class")
    async def groups(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> dict[str, str]:
        registry.schema.register_schema(
            schema=do_car_person_schema_unregistered(), branch=default_branch_scope_class.name
        )
        default_branch_scope_class.update_schema_hash()
        return await create_groups(db=db, names=GROUP_NAMES)

    @pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in OWNER_WRITE_TEST_CASES])
    async def test_null_changes_nothing_and_a_group_replaces_the_own_owners(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        groups: dict[str, str],
        test_case: OwnerWriteTestCase,
    ) -> None:
        branch = default_branch_scope_class
        server_team, security_team = groups["server-team"], groups["security-team"]
        own_owners = None if test_case.own_owners is None else [groups[name] for name in test_case.own_owners]
        person = await add_node(db=db, kind="TestPerson", name=f"person-{test_case.name}")
        car_id = await create(
            db,
            branch,
            CREATE_CAR,
            "TestCar",
            name=f"car-{test_case.name}",
            person=person.id,
            owners=[{"id": server_team}],
            color={"value": "#111111", "owners": None if own_owners is None else [{"id": id_} for id_ in own_owners]},
        )

        before = await read_node(db=db, branch=branch, query=READ_COLOR, kind="TestCar", node_id=car_id)
        await run(db=db, branch=branch, query=UPDATE_COLOR, variables={"id": car_id, "color": {"owner": None}})
        after_null = await read_node(db=db, branch=branch, query=READ_COLOR, kind="TestCar", node_id=car_id)
        await run(db=db, branch=branch, query=UPDATE_COLOR, variables={"id": car_id, "color": {"owner": security_team}})
        after_write = await read_node(db=db, branch=branch, query=READ_COLOR, kind="TestCar", node_id=car_id)

        ownership = from_node(car_id, server_team) if own_owners is None else own(car_id, *own_owners)
        owner = None if test_case.owner is None else {"id": groups[test_case.owner]}
        assert before == {"color": {"value": "#111111", "owner": owner, "ownership": ownership}}
        assert after_null == before
        assert after_write == {
            "color": {"value": "#111111", "owner": {"id": security_team}, "ownership": own(car_id, security_team)}
        }

    async def test_owners_of_a_relationship_without_peers_leave_the_owners_of_its_later_links_unchanged(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        server_team, network_team, security_team = (groups[name] for name in GROUP_NAMES)
        person = await add_node(db=db, kind="TestPerson", name="person-with-links")

        await run(
            db=db, branch=branch, query=SET_CARS_OWNERS, variables={"id": person.id, "owners": [{"id": network_team}]}
        )
        without_peers = await read_node(db=db, branch=branch, query=READ_CARS, kind="TestPerson", node_id=person.id)
        car_id = await create(
            db,
            branch,
            CREATE_CAR_WITH_LINK_OWNER,
            "TestCar",
            name="car-with-link-owner",
            person=person.id,
            link_owner=server_team,
        )
        with_link = await read_node(db=db, branch=branch, query=READ_CARS, kind="TestPerson", node_id=person.id)
        await run(
            db=db,
            branch=branch,
            query=SET_LINK_OWNER,
            variables={"id": car_id, "person": person.id, "link_owner": security_team},
        )
        after_link_change = await read_node(db=db, branch=branch, query=READ_CARS, kind="TestPerson", node_id=person.id)

        field_owners = own(person.id, network_team)
        assert without_peers == {"cars": {"count": 0, "ownership": field_owners, "edges": []}}

        def cars(link_owner: str) -> dict[str, Any]:
            edge = {"ownership": field_owners, "properties": {"owner": {"id": link_owner}}, "node": {"id": car_id}}
            return {"cars": {"count": 1, "ownership": field_owners, "edges": [edge]}}

        assert with_link == cars(server_team)
        assert after_link_change == cars(security_team)
