from __future__ import annotations

from datetime import datetime
from operator import itemgetter
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core import registry
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionAction, PermissionDecision
from infrahub.core.manager import NodeManager
from infrahub.exceptions import PermissionDeniedError
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.api.dependencies import build_graphql_query_permission_checker
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql_query
from tests.helpers.ownership import add_node, create_groups
from tests.helpers.schema.ownership import OWNERSHIP_SCHEMA

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

GROUP_NAMES = ("dc-emea", "dc-security", "network-emea")

OWNERSHIP_FIELDS = """
ownership {
    state
    origin
    origin_node { id kind is_deleted }
    owners { id kind display_label hfid is_deleted }
}
"""

READ_OWNERSHIP = """
query($ids: [ID]) {
    %(kind)s(ids: $ids) { edges { node { id } node_metadata { %(fields)s } } }
}
"""

FILTER = """
query($owners: [ID], $no_owner: Boolean, $ids: [ID]) {
    %(kind)s(node_metadata__owners__ids: $owners, node_metadata__owners__isnull: $no_owner, ids: $ids) {
        count
        edges { node { id } node_metadata { ownership { state origin origin_node { id } owners { id } } } }
    }
}
"""

SET_OWNERS = """
mutation($id: String!, $owners: [MetadataNodeInput!]) {
    %(kind)sUpdate(data: {id: $id, node_metadata: {owners: $owners}}) { ok }
}
"""

READ_AUDIT = """
query($ids: [ID]) {
    %(kind)s(ids: $ids) { edges { node { id } node_metadata { updated_at updated_by { id } } } }
}
"""


async def run(
    db: InfrahubDatabase,
    branch: Branch,
    query: str,
    variables: dict[str, Any] | None = None,
    session: AccountSession | None = None,
) -> dict[str, Any]:
    result = await graphql_query(query=query, db=db, branch=branch, variables=variables, account_session=session)
    assert result.errors is None, result.errors
    assert result.data
    return result.data


async def set_owners(
    db: InfrahubDatabase,
    branch: Branch,
    node: Node,
    owner_ids: list[str] | None,
    session: AccountSession | None = None,
) -> None:
    """Set own owners with a list, "no owner" with an empty list, and inherit with None."""
    owners = None if owner_ids is None else [{"id": owner_id} for owner_id in owner_ids]
    await run(
        db=db,
        branch=branch,
        query=SET_OWNERS % {"kind": node.get_kind()},
        variables={"id": node.id, "owners": owners},
        session=session,
    )


async def read_metadata(
    db: InfrahubDatabase, branch: Branch, query: str, *nodes: Node, session: AccountSession | None = None
) -> dict[str, dict[str, Any]]:
    """Return the `node_metadata` of each node, by node ID. The nodes are of one kind."""
    kind = nodes[0].get_kind()
    data = await run(
        db=db,
        branch=branch,
        query=query % {"kind": kind, "fields": OWNERSHIP_FIELDS},
        variables={"ids": [node.id for node in nodes]},
        session=session,
    )
    return {edge["node"]["id"]: edge["node_metadata"] for edge in data[kind]["edges"]}


async def read_ownership(db: InfrahubDatabase, branch: Branch, node: Node) -> dict[str, Any]:
    return (await read_metadata(db, branch, READ_OWNERSHIP, node))[node.id]["ownership"]


async def filter_nodes(
    db: InfrahubDatabase,
    branch: Branch,
    kind: str,
    owners: list[str] | None = None,
    no_owner: bool | None = None,
    ids: list[str] | None = None,
) -> tuple[int, dict[str, dict[str, Any]]]:
    """Return the count of the list and the `ownership` of each node of the list, by node ID."""
    variables = {"owners": owners, "no_owner": no_owner, "ids": ids}
    data = await run(
        db=db,
        branch=branch,
        query=FILTER % {"kind": kind},
        variables={name: value for name, value in variables.items() if value is not None},
    )
    edges = data[kind]["edges"]
    return data[kind]["count"], {edge["node"]["id"]: edge["node_metadata"]["ownership"] for edge in edges}


def origin_node(node: Node) -> dict[str, Any]:
    return {"id": node.id, "kind": node.get_kind(), "is_deleted": False}


def own(node: Node, *owner_ids: str) -> dict[str, Any]:
    """Return the short `ownership` of a node with own owners, as the filter query reads it."""
    return {"state": "OWNERS", "origin": "SELF", "origin_node": {"id": node.id}, "owners": owned_by(*owner_ids)}


def inherited(parent: Node, *owner_ids: str) -> dict[str, Any]:
    """Return the short `ownership` of a node that inherits from its parent, as the filter query reads it."""
    return {"state": "INHERIT", "origin": "PARENT", "origin_node": {"id": parent.id}, "owners": owned_by(*owner_ids)}


def owned_by(*owner_ids: str) -> list[dict[str, str]]:
    return [{"id": owner_id} for owner_id in sorted(owner_ids)]


@pytest.fixture(scope="class")
async def groups(
    db: InfrahubDatabase, default_branch_scope_class: Branch, register_core_models_schema_scope_class: SchemaBranch
) -> dict[str, str]:
    registry.schema.register_schema(schema=OWNERSHIP_SCHEMA, branch=default_branch_scope_class.name)
    default_branch_scope_class.update_schema_hash()
    return await create_groups(db=db, names=GROUP_NAMES)


def group_owners(groups: dict[str, str], *names: str) -> list[dict[str, Any]]:
    """Return the owners as the full `ownership` query reads them, in the order of their IDs."""
    owners = [
        {
            "id": groups[name],
            "kind": InfrahubKind.ACCOUNTGROUP,
            "display_label": name,
            "hfid": [name],
            "is_deleted": False,
        }
        for name in names
    ]
    return sorted(owners, key=itemgetter("id"))


class TestNodeOwnerFilters:
    """The racks are the devices of the scenarios, and the devices under a rack are its interfaces."""

    @pytest.fixture(scope="class")
    async def nodes(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> dict[str, Node]:
        """Each rack holds two devices. The name of a rack gives its owners."""
        branch = default_branch_scope_class
        tenant = await add_node(db=db, kind="TestTenant", name="tenant-of-racks")
        nodes: dict[str, Node] = {}
        rack_owners = {
            "emea": ["dc-emea"],
            "emea-and-security": ["dc-emea", "dc-security"],
            "unowned-1": None,
            "unowned-2": None,
        }
        for name, owner_names in rack_owners.items():
            rack = await add_node(db=db, kind="TestRack", name=f"rack-{name}", tenant=tenant)
            nodes[f"rack-{name}"] = rack
            for index in (1, 2):
                nodes[f"device-{name}-{index}"] = await add_node(
                    db=db, kind="TestDevice", name=f"device-{name}-{index}", rack=rack
                )
            if owner_names:
                await set_owners(db=db, branch=branch, node=rack, owner_ids=[groups[owner] for owner in owner_names])
        return nodes

    async def test_owner_filter_lists_the_owned_racks_and_their_devices_with_the_rack_as_origin(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str], nodes: dict[str, Node]
    ) -> None:
        branch = default_branch_scope_class
        emea, security = groups["dc-emea"], groups["dc-security"]

        racks = await filter_nodes(db=db, branch=branch, kind="TestRack", owners=[emea])
        devices = await filter_nodes(db=db, branch=branch, kind="TestDevice", owners=[emea])

        assert racks == (
            2,
            {
                nodes["rack-emea"].id: own(nodes["rack-emea"], emea),
                nodes["rack-emea-and-security"].id: own(nodes["rack-emea-and-security"], emea, security),
            },
        )
        assert devices == (
            4,
            {
                **{nodes[f"device-emea-{index}"].id: inherited(nodes["rack-emea"], emea) for index in (1, 2)},
                **{
                    nodes[f"device-emea-and-security-{index}"].id: inherited(
                        nodes["rack-emea-and-security"], emea, security
                    )
                    for index in (1, 2)
                },
            },
        )

    async def test_no_owner_filter_lists_the_other_racks_with_their_count(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, nodes: dict[str, Node]
    ) -> None:
        no_owner = {"state": "INHERIT", "origin": None, "origin_node": None, "owners": []}

        racks = await filter_nodes(db=db, branch=default_branch_scope_class, kind="TestRack", no_owner=True)

        assert racks == (2, {nodes["rack-unowned-1"].id: no_owner, nodes["rack-unowned-2"].id: no_owner})

    async def test_filter_by_two_owners_lists_a_rack_with_both_owners_one_time(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str], nodes: dict[str, Node]
    ) -> None:
        emea, security = groups["dc-emea"], groups["dc-security"]

        racks = await filter_nodes(db=db, branch=default_branch_scope_class, kind="TestRack", owners=[emea, security])

        assert racks == (
            2,
            {
                nodes["rack-emea"].id: own(nodes["rack-emea"], emea),
                nodes["rack-emea-and-security"].id: own(nodes["rack-emea-and-security"], emea, security),
            },
        )

    async def test_device_set_to_no_owner_and_back_to_inherit(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str], nodes: dict[str, Node]
    ) -> None:
        branch = default_branch_scope_class
        device, rack = nodes["device-emea-1"], nodes["rack-emea"]
        emea = groups["dc-emea"]

        await set_owners(db=db, branch=branch, node=device, owner_ids=[])
        with_no_owner = await read_ownership(db=db, branch=branch, node=device)
        no_owner_list = await filter_nodes(db=db, branch=branch, kind="TestDevice", no_owner=True, ids=[device.id])
        owner_list = await filter_nodes(db=db, branch=branch, kind="TestDevice", owners=[emea], ids=[device.id])

        await set_owners(db=db, branch=branch, node=device, owner_ids=None)
        with_inherit = await read_ownership(db=db, branch=branch, node=device)
        owner_list_after = await filter_nodes(db=db, branch=branch, kind="TestDevice", owners=[emea], ids=[device.id])

        assert with_no_owner == {
            "state": "NO_OWNER",
            "origin": "SELF",
            "origin_node": origin_node(device),
            "owners": [],
        }
        assert no_owner_list == (
            1,
            {device.id: {"state": "NO_OWNER", "origin": "SELF", "origin_node": {"id": device.id}, "owners": []}},
        )
        assert owner_list == (0, {})
        assert with_inherit == {
            "state": "INHERIT",
            "origin": "PARENT",
            "origin_node": origin_node(rack),
            "owners": group_owners(groups, "dc-emea"),
        }
        assert owner_list_after == (1, {device.id: inherited(rack, emea)})


class TestNodeOwners:
    async def test_site_shows_the_owners_of_its_country(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        country = await add_node(db=db, kind="TestSite", name="country")
        site = await add_node(db=db, kind="TestSite", name="site-of-country", parent=country)

        await set_owners(db=db, branch=branch, node=country, owner_ids=[groups["network-emea"]])

        assert await read_ownership(db=db, branch=branch, node=site) == {
            "state": "INHERIT",
            "origin": "PARENT",
            "origin_node": origin_node(country),
            "owners": group_owners(groups, "network-emea"),
        }

    async def test_parent_relationship_peer_wins_over_the_hierarchy_parent(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        site = await add_node(db=db, kind="TestSite", name="site-of-rack")
        tenant = await add_node(db=db, kind="TestTenant", name="tenant-of-rack")
        rack = await add_node(db=db, kind="TestRack", name="rack-with-two-parents", parent=site, tenant=tenant)

        await set_owners(db=db, branch=branch, node=site, owner_ids=[groups["dc-emea"]])
        await set_owners(db=db, branch=branch, node=tenant, owner_ids=[groups["network-emea"]])

        assert await read_ownership(db=db, branch=branch, node=rack) == {
            "state": "INHERIT",
            "origin": "PARENT",
            "origin_node": origin_node(tenant),
            "owners": group_owners(groups, "network-emea"),
        }

    async def test_deleted_owner_group_shows_as_deleted_and_a_new_group_with_its_name_owns_nothing(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch
    ) -> None:
        branch = default_branch_scope_class
        group = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="dc-deleted")
        tenant = await add_node(db=db, kind="TestTenant", name="tenant-of-deleted-group")
        rack = await add_node(db=db, kind="TestRack", name="rack-of-deleted-group", tenant=tenant)
        device = await add_node(db=db, kind="TestDevice", name="device-of-deleted-group", rack=rack)
        await set_owners(db=db, branch=branch, node=rack, owner_ids=[group.id])
        owned_ids = [rack.id, device.id]
        no_owner_before = {
            kind: await filter_nodes(db=db, branch=branch, kind=kind, no_owner=True, ids=owned_ids)
            for kind in ("TestRack", "TestDevice")
        }

        await group.delete(db=db)
        after_delete = await read_ownership(db=db, branch=branch, node=rack)
        no_owner_after = {
            kind: (await filter_nodes(db=db, branch=branch, kind=kind, no_owner=True, ids=owned_ids))[1].keys()
            for kind in ("TestRack", "TestDevice")
        }
        new_group = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="dc-deleted")
        after_new_group = await read_ownership(db=db, branch=branch, node=rack)
        new_group_list = await filter_nodes(db=db, branch=branch, kind="TestRack", owners=[new_group.id])

        assert no_owner_before == {"TestRack": (0, {}), "TestDevice": (0, {})}
        assert after_delete == {
            "state": "OWNERS",
            "origin": "SELF",
            "origin_node": origin_node(rack),
            "owners": [{"id": group.id, "kind": None, "display_label": None, "hfid": None, "is_deleted": True}],
        }
        assert {kind: set(ids) for kind, ids in no_owner_after.items()} == {
            "TestRack": {rack.id},
            "TestDevice": {device.id},
        }
        assert after_new_group == after_delete
        assert new_group_list == (0, {})

    async def test_owner_of_another_kind_refuses_the_whole_update(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        repository = await add_node(
            db=db,
            kind=InfrahubKind.READONLYREPOSITORY,
            name="repository",
            location="git@example.com:repo.git",
            ref="main",
        )
        tenant = await add_node(db=db, kind="TestTenant", name="tenant-before-refusal")
        await set_owners(db=db, branch=branch, node=tenant, owner_ids=[groups["dc-emea"]])

        result = await graphql_query(
            query="""
            mutation($id: String!, $owners: [MetadataNodeInput!]) {
                TestTenantUpdate(
                    data: {id: $id, name: {value: "tenant-after-refusal"}, node_metadata: {owners: $owners}}
                ) { ok }
            }
            """,
            db=db,
            branch=branch,
            variables={"id": tenant.id, "owners": [{"id": groups["dc-security"]}, {"id": repository.id}]},
        )

        assert [error.message for error in result.errors or []] == [
            f"Only an account or an account group can be an owner, not: {repository.id} at node_metadata.owners"
        ]
        stored = await NodeManager.get_one(db=db, branch=branch, id=tenant.id, raise_on_error=True)
        assert stored.name.value == "tenant-before-refusal"
        assert (await read_ownership(db=db, branch=branch, node=tenant))["owners"] == group_owners(groups, "dc-emea")

    async def test_owner_change_updates_the_audit_metadata_of_the_changed_node_only(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        account = await add_node(db=db, kind=InfrahubKind.ACCOUNT, name="jane", password="a-password")
        session = AccountSession(authenticated=True, auth_type=AuthType.API, account_id=account.id)
        tenant = await add_node(db=db, kind="TestTenant", name="tenant-audit")
        rack = await add_node(db=db, kind="TestRack", name="rack-audit", tenant=tenant)
        device = await add_node(db=db, kind="TestDevice", name="device-audit", rack=rack)
        rack_before = (await read_metadata(db, branch, READ_AUDIT, rack))[rack.id]
        device_before = (await read_metadata(db, branch, READ_AUDIT, device))[device.id]

        await set_owners(db=db, branch=branch, node=rack, owner_ids=[groups["dc-emea"]], session=session)

        rack_after = (await read_metadata(db, branch, READ_AUDIT, rack))[rack.id]
        device_after = (await read_metadata(db, branch, READ_AUDIT, device))[device.id]
        assert datetime.fromisoformat(rack_after["updated_at"]) > datetime.fromisoformat(rack_before["updated_at"])
        assert rack_after["updated_by"] == {"id": account.id}
        assert device_after == device_before


class TestNodeOwnersPermissions:
    @pytest.fixture(scope="class")
    async def session(
        self, db: InfrahubDatabase, groups: dict[str, str], default_permission_backend_scope_class: None
    ) -> AccountSession:
        """The session of an account with all permissions on the `Test` namespace and on the default branch only."""
        object_permission = await add_node(
            db=db,
            kind=InfrahubKind.OBJECTPERMISSION,
            namespace="Test",
            name="*",
            action=PermissionAction.ANY.value,
            decision=PermissionDecision.ALLOW_ALL.value,
        )
        branch_permission = await add_node(
            db=db,
            kind=InfrahubKind.GLOBALPERMISSION,
            action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value,
            decision=PermissionDecision.ALLOW_ALL.value,
        )
        role = await add_node(
            db=db,
            kind=InfrahubKind.ACCOUNTROLE,
            name="test-namespace",
            permissions=[object_permission, branch_permission],
        )
        account = await add_node(db=db, kind=InfrahubKind.ACCOUNT, name="auditor", password="a-password")
        await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="auditors", roles=[role], members=[account])
        return AccountSession(authenticated=True, auth_type=AuthType.API, account_id=account.id)

    @staticmethod
    async def check_permissions(
        db: InfrahubDatabase,
        branch: Branch,
        session: AccountSession,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> None:
        """Run the permission checks of a GraphQL request."""
        gql_params = await prepare_graphql_params(db=db, branch=branch, account_session=session)
        analyzed_query = InfrahubGraphQLQueryAnalyzer(
            query=query,
            query_variables=variables,
            schema=gql_params.schema,
            branch=branch,
            schema_branch=registry.schema.get_schema_branch(name=branch.name),
        )
        await build_graphql_query_permission_checker().check(
            db=db, account_session=session, analyzed_query=analyzed_query, query_parameters=gql_params, branch=branch
        )

    async def test_user_without_view_permission_on_account_groups_views_the_owners(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str], session: AccountSession
    ) -> None:
        branch = default_branch_scope_class
        tenant = await add_node(db=db, kind="TestTenant", name="tenant-read-by-auditor")
        await set_owners(db=db, branch=branch, node=tenant, owner_ids=[groups["dc-emea"]])
        query = READ_OWNERSHIP % {"kind": "TestTenant", "fields": OWNERSHIP_FIELDS}

        with pytest.raises(PermissionDeniedError, match=r":AccountGroup:view:"):
            await self.check_permissions(
                db=db,
                branch=branch,
                session=session,
                query="query { CoreAccountGroup { edges { node { name { value } } } } }",
            )
        await self.check_permissions(db=db, branch=branch, session=session, query=query, variables={"ids": [tenant.id]})
        metadata = await read_metadata(db, branch, READ_OWNERSHIP, tenant, session=session)

        assert metadata[tenant.id]["ownership"]["owners"] == group_owners(groups, "dc-emea")

    async def test_user_with_update_permission_changes_the_owners_of_a_node_of_another_team(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str], session: AccountSession
    ) -> None:
        branch = default_branch_scope_class
        tenant = await add_node(db=db, kind="TestTenant", name="tenant-of-another-team")
        await set_owners(db=db, branch=branch, node=tenant, owner_ids=[groups["dc-emea"]])
        query = SET_OWNERS % {"kind": "TestTenant"}

        await self.check_permissions(
            db=db,
            branch=branch,
            session=session,
            query=query,
            variables={"id": tenant.id, "owners": [{"id": groups["network-emea"]}]},
        )
        await set_owners(db=db, branch=branch, node=tenant, owner_ids=[groups["network-emea"]], session=session)

        assert (await read_ownership(db=db, branch=branch, node=tenant))["owners"] == group_owners(
            groups, "network-emea"
        )
