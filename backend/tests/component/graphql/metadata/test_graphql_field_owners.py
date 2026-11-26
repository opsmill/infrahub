from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from tests.helpers.ownership import add_node, create, create_groups, from_node, own, read_node, run

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

GROUP_NAMES = ("server-team", "network-team", "security-team")
PEER_COUNT = 48

SERVER_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="Address", namespace="Test", attributes=[AttributeSchema(name="name", kind="Text", unique=True)]
        ),
        NodeSchema(
            name="Server",
            namespace="Test",
            generate_template=True,
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="description", kind="Text", optional=True),
            ],
            relationships=[
                RelationshipSchema(
                    name="ip_addresses",
                    peer="TestAddress",
                    optional=True,
                    cardinality=RelationshipCardinality.MANY,
                    identifier="server__ip_addresses",
                ),
                RelationshipSchema(
                    name="primary_address",
                    peer="TestAddress",
                    optional=True,
                    cardinality=RelationshipCardinality.ONE,
                    identifier="server__primary_address",
                ),
            ],
        ),
    ]
)

OWNERSHIP = "ownership { state origin origin_node { id } owners { id } }"

READ_FIELDS = """
query($ids: [ID]) {
    TestServer(ids: $ids) {
        edges {
            node {
                name { %(ownership)s }
                description { %(ownership)s }
                ip_addresses { count %(ownership)s }
                primary_address { %(ownership)s }
            }
        }
    }
}
""" % {"ownership": OWNERSHIP}

READ_PEERS = """
query($ids: [ID]) {
    TestServer(ids: $ids) { edges { node { ip_addresses { edges { %(ownership)s node { id } } } } } }
}
""" % {"ownership": OWNERSHIP}

READ_LINK_OWNERS = """
query($ids: [ID]) {
    TestServer(ids: $ids) { edges { node { ip_addresses { edges { ownership { owners { id } } } } } } }
}
"""

CREATE_SERVER = """
mutation($name: String!, $owners: [MetadataNodeInput!], $addresses: [RelatedNodeInput]) {
    TestServerCreate(data: {name: {value: $name}, ip_addresses: $addresses, node_metadata: {owners: $owners}}) {
        object { id }
    }
}
"""

CREATE_SERVER_FROM_TEMPLATE = """
mutation($name: String!, $owners: [MetadataNodeInput!], $template: String!) {
    TestServerCreate(
        data: {name: {value: $name}, object_template: {id: $template}, node_metadata: {owners: $owners}}
    ) { object { id } }
}
"""

SET_FIELD_OWNERS = """
mutation($id: String!, $field_owners: [FieldOwnersInput!]) {
    TestServerUpdate(data: {id: $id, node_metadata: {field_owners: $field_owners}}) { ok }
}
"""

ATTACH_PROFILE = """
mutation($id: String!, $profile: String!) {
    TestServerUpdate(data: {id: $id, profiles: [{id: $profile}]}) { ok }
}
"""

CREATE_PROFILE = """
mutation($name: String!, $given: [FieldOwnersInput!]) {
    ProfileTestServerCreate(data: {profile_name: {value: $name}, node_metadata: {target_field_owners: $given}}) {
        object { id }
    }
}
"""

CREATE_TEMPLATE = """
mutation($name: String!, $given: [FieldOwnersInput!]) {
    TemplateTestServerCreate(data: {template_name: {value: $name}, node_metadata: {target_field_owners: $given}}) {
        object { id }
    }
}
"""


def owners_input(*owner_ids: str) -> list[dict[str, str]]:
    return [{"id": owner_id} for owner_id in owner_ids]


def fields_of_node(server_id: str, owner_id: str, peer_count: int = 0) -> dict[str, Any]:
    """Return the fields of a server whose fields all take the owners of the server."""
    return {
        "name": {"ownership": from_node(server_id, owner_id)},
        "description": {"ownership": from_node(server_id, owner_id)},
        "ip_addresses": {"count": peer_count, "ownership": from_node(server_id, owner_id)},
        "primary_address": {"ownership": from_node(server_id, owner_id)},
    }


class TestFieldOwners:
    """Each server is owned by the server team, and the tests give owners to its fields."""

    @pytest.fixture(scope="class")
    async def groups(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> dict[str, str]:
        registry.schema.register_schema(schema=SERVER_SCHEMA, branch=default_branch_scope_class.name)
        default_branch_scope_class.update_schema_hash()
        return await create_groups(db=db, names=GROUP_NAMES)

    @staticmethod
    async def set_field_owners(
        db: InfrahubDatabase, branch: Branch, server_id: str, field: str, owners: list[dict[str, str]] | None
    ) -> None:
        await run(
            db=db,
            branch=branch,
            query=SET_FIELD_OWNERS,
            variables={"id": server_id, "field_owners": [{"field": field, "owners": owners}]},
        )

    async def test_relationship_without_peers_takes_own_owners_and_goes_back_to_the_owners_of_the_server(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        server_team, network_team = groups["server-team"], groups["network-team"]
        server_id = await create(
            db, branch, CREATE_SERVER, "TestServer", name="srv01", owners=owners_input(server_team)
        )

        await self.set_field_owners(db, branch, server_id, field="ip_addresses", owners=owners_input(network_team))
        with_own_owners = await read_node(db=db, branch=branch, query=READ_FIELDS, kind="TestServer", node_id=server_id)
        await self.set_field_owners(db, branch, server_id, field="description", owners=[])
        with_no_owner = await read_node(db=db, branch=branch, query=READ_FIELDS, kind="TestServer", node_id=server_id)
        await self.set_field_owners(db, branch, server_id, field="ip_addresses", owners=None)
        after_reset = await read_node(db=db, branch=branch, query=READ_FIELDS, kind="TestServer", node_id=server_id)

        of_node = fields_of_node(server_id, server_team)
        assert with_own_owners == of_node | {"ip_addresses": {"count": 0, "ownership": own(server_id, network_team)}}
        assert with_no_owner == with_own_owners | {"description": {"ownership": own(server_id)}}
        assert after_reset == of_node | {"description": {"ownership": own(server_id)}}

    async def test_relationship_with_many_peers_gives_one_ownership_for_the_field_and_all_its_links(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        server_team, network_team = groups["server-team"], groups["network-team"]
        address_ids = [
            (await add_node(db=db, kind="TestAddress", name=f"10.0.0.{index}")).id for index in range(PEER_COUNT)
        ]
        server_id = await create(
            db,
            branch,
            CREATE_SERVER,
            "TestServer",
            name="srv-many-addresses",
            owners=owners_input(server_team),
            addresses=owners_input(*address_ids),
        )

        await self.set_field_owners(db, branch, server_id, field="ip_addresses", owners=owners_input(network_team))
        fields = await read_node(db=db, branch=branch, query=READ_FIELDS, kind="TestServer", node_id=server_id)
        links = await read_node(db=db, branch=branch, query=READ_PEERS, kind="TestServer", node_id=server_id)

        field_owners = own(server_id, network_team)
        assert fields == fields_of_node(server_id, server_team, peer_count=PEER_COUNT) | {
            "ip_addresses": {"count": PEER_COUNT, "ownership": field_owners}
        }
        edges = links["ip_addresses"]["edges"]
        assert sorted(edge["node"]["id"] for edge in edges) == sorted(address_ids)
        assert [edge["ownership"] for edge in edges] == [field_owners] * PEER_COUNT

    async def test_links_give_their_owners_when_the_query_asks_for_no_field_of_the_peers(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        server_team, network_team = groups["server-team"], groups["network-team"]
        address_ids = [(await add_node(db=db, kind="TestAddress", name=f"10.1.0.{index}")).id for index in range(2)]
        server_id = await create(
            db,
            branch,
            CREATE_SERVER,
            "TestServer",
            name="srv-link-owners",
            owners=owners_input(server_team),
            addresses=owners_input(*address_ids),
        )
        await self.set_field_owners(db, branch, server_id, field="ip_addresses", owners=owners_input(network_team))

        links = await read_node(db=db, branch=branch, query=READ_LINK_OWNERS, kind="TestServer", node_id=server_id)

        assert links["ip_addresses"]["edges"] == [{"ownership": {"owners": [{"id": network_team}]}}] * 2

    async def test_profile_gives_owners_to_a_relationship_and_own_owners_of_the_relationship_win(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        groups: dict[str, str],
        session_admin_scope_class: AccountSession,
    ) -> None:
        branch = default_branch_scope_class
        server_team, network_team, security_team = (groups[name] for name in GROUP_NAMES)
        profile_id = await create(
            db,
            branch,
            CREATE_PROFILE,
            "ProfileTestServer",
            session=session_admin_scope_class,
            name="Server ownership",
            given=[{"field": "ip_addresses", "owners": owners_input(network_team)}],
        )
        server_id = await create(
            db, branch, CREATE_SERVER, "TestServer", name="srv-with-profile", owners=owners_input(server_team)
        )
        owned_id = await create(
            db, branch, CREATE_SERVER, "TestServer", name="srv-with-own-owners", owners=owners_input(server_team)
        )
        await self.set_field_owners(db, branch, owned_id, field="ip_addresses", owners=owners_input(security_team))

        for node_id in (server_id, owned_id):
            await run(
                db=db,
                branch=branch,
                query=ATTACH_PROFILE,
                variables={"id": node_id, "profile": profile_id},
                session=session_admin_scope_class,
            )
        server = await read_node(db=db, branch=branch, query=READ_FIELDS, kind="TestServer", node_id=server_id)
        owned = await read_node(db=db, branch=branch, query=READ_FIELDS, kind="TestServer", node_id=owned_id)

        from_profile = {
            "state": "INHERIT",
            "origin": "PROFILE",
            "origin_node": {"id": profile_id},
            "owners": [{"id": network_team}],
        }
        assert server == fields_of_node(server_id, server_team) | {
            "ip_addresses": {"count": 0, "ownership": from_profile}
        }
        assert owned == fields_of_node(owned_id, server_team) | {
            "ip_addresses": {"count": 0, "ownership": own(owned_id, security_team)}
        }

    async def test_template_gives_owners_to_a_relationship_of_the_servers_created_from_it(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        groups: dict[str, str],
        session_admin_scope_class: AccountSession,
    ) -> None:
        branch = default_branch_scope_class
        server_team, network_team = groups["server-team"], groups["network-team"]
        template_id = await create(
            db,
            branch,
            CREATE_TEMPLATE,
            "TemplateTestServer",
            session=session_admin_scope_class,
            name="standard-server",
            given=[{"field": "ip_addresses", "owners": owners_input(network_team)}],
        )

        server_id = await create(
            db,
            branch,
            CREATE_SERVER_FROM_TEMPLATE,
            "TestServer",
            session=session_admin_scope_class,
            name="srv-from-template",
            owners=owners_input(server_team),
            template=template_id,
        )
        server = await read_node(db=db, branch=branch, query=READ_FIELDS, kind="TestServer", node_id=server_id)

        assert server == fields_of_node(server_id, server_team) | {
            "ip_addresses": {
                "count": 0,
                "ownership": {
                    "state": "INHERIT",
                    "origin": "TEMPLATE",
                    "origin_node": {"id": template_id},
                    "owners": [{"id": network_team}],
                },
            }
        }


READ_THINGS_WITH_DESCENDANTS = """
query($name: String!) {
    LocationRegion(name__value: $name) {
        edges { node { things(include_descendants: true) { edges { %(ownership)s node { name { value } } } } } }
    }
}
""" % {"ownership": OWNERSHIP}


async def test_links_of_descendants_give_the_owners_of_the_field_of_the_node_that_holds_them(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_thing: dict[str, Node]
) -> None:
    groups = await create_groups(db=db, names=GROUP_NAMES)
    europe_id = hierarchical_location_data_thing["europe"].id
    paris_id = hierarchical_location_data_thing["paris"].id
    for kind, node_id, group in (
        ("LocationRegion", europe_id, "server-team"),
        ("LocationSite", paris_id, "network-team"),
    ):
        await run(
            db=db,
            branch=default_branch,
            query="""
            mutation($id: String!, $field_owners: [FieldOwnersInput!]) {
                %sUpdate(data: {id: $id, node_metadata: {field_owners: $field_owners}}) { ok }
            }
            """
            % kind,
            variables={"id": node_id, "field_owners": [{"field": "things", "owners": [{"id": groups[group]}]}]},
        )

    data = await run(db=db, branch=default_branch, query=READ_THINGS_WITH_DESCENDANTS, variables={"name": "europe"})

    edges = data["LocationRegion"]["edges"][0]["node"]["things"]["edges"]
    no_owner_anywhere = {"state": "INHERIT", "origin": None, "origin_node": None, "owners": []}
    ownership_by_thing = {edge["node"]["name"]["value"]: edge["ownership"] for edge in edges}
    assert ownership_by_thing == {
        "thing-europe": own(europe_id, groups["server-team"]),
        "thing-paris": own(paris_id, groups["network-team"]),
        "thing-london": no_owner_anywhere,
        "thing-paris-r1": no_owner_anywhere,
        "thing-paris-r2": no_owner_anywhere,
        "thing-london-r1": no_owner_anywhere,
        "thing-london-r2": no_owner_anywhere,
    }
