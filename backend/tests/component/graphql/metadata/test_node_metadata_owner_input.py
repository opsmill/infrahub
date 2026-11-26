from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from tests.helpers.graphql import graphql_query
from tests.helpers.ownership import create_groups
from tests.helpers.schema.ownership import OWNERSHIP_SCHEMA

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

OWNERSHIP_FIELDS = """
ownership {
    state
    origin
    origin_node { id }
    owners { id kind display_label hfid is_deleted }
}
"""


async def run(db: InfrahubDatabase, branch: Branch, query: str, variables: dict[str, Any] | None = None) -> Any:
    result = await graphql_query(query=query, db=db, branch=branch, variables=variables)
    assert result.errors is None, result.errors
    return result.data


async def read_ownership(db: InfrahubDatabase, branch: Branch, kind: str, node_id: str) -> dict[str, Any]:
    data = await run(
        db=db,
        branch=branch,
        query=f'query {{ {kind}(ids: ["{node_id}"]) {{ edges {{ node_metadata {{ {OWNERSHIP_FIELDS} }} }} }} }}',
    )
    return data[kind]["edges"][0]["node_metadata"]["ownership"]


def own_owner(node_id: str, group_id: str, name: str) -> dict[str, Any]:
    return {
        "state": "OWNERS",
        "origin": "SELF",
        "origin_node": {"id": node_id},
        "owners": [
            {
                "id": group_id,
                "kind": InfrahubKind.ACCOUNTGROUP,
                "display_label": name,
                "hfid": [name],
                "is_deleted": False,
            }
        ],
    }


UPDATE_TENANT = """
mutation($id: String!, $name: String!, $metadata: NodeMetadataInput) {
    TestTenantUpdate(data: {id: $id, name: {value: $name}, node_metadata: $metadata}) { ok }
}
"""


class TestNodeMetadataOwnerInput:
    @pytest.fixture(scope="class")
    async def groups(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> dict[str, str]:
        registry.schema.register_schema(schema=OWNERSHIP_SCHEMA, branch=default_branch_scope_class.name)
        default_branch_scope_class.update_schema_hash()
        return await create_groups(db=db)

    async def test_create_sets_owners_and_update_keeps_them_when_the_key_is_left_out(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        data = await run(
            db=db,
            branch=branch,
            query="""
            mutation($group: String!) {
                TestTenantCreate(data: {name: {value: "tenant-create"}, node_metadata: {owners: [{id: $group}]}}) {
                    ok
                    object { id }
                }
            }
            """,
            variables={"group": groups["dc-emea"]},
        )
        tenant_id = data["TestTenantCreate"]["object"]["id"]
        assert await read_ownership(db=db, branch=branch, kind="TestTenant", node_id=tenant_id) == own_owner(
            node_id=tenant_id, group_id=groups["dc-emea"], name="dc-emea"
        )

        await run(db=db, branch=branch, query=UPDATE_TENANT, variables={"id": tenant_id, "name": "tenant-renamed"})

        tenant = await NodeManager.get_one(db=db, branch=branch, id=tenant_id, raise_on_error=True)
        assert tenant.name.value == "tenant-renamed"
        assert await read_ownership(db=db, branch=branch, kind="TestTenant", node_id=tenant_id) == own_owner(
            node_id=tenant_id, group_id=groups["dc-emea"], name="dc-emea"
        )

    async def test_update_sets_no_owner_then_inherit(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        data = await run(
            db=db,
            branch=branch,
            query="""
            mutation {
                TestTenantCreate(data: {name: {value: "tenant-states"}}) { object { id } }
            }
            """,
        )
        tenant_id = data["TestTenantCreate"]["object"]["id"]
        inherit = {"state": "INHERIT", "origin": None, "origin_node": None, "owners": []}
        assert await read_ownership(db=db, branch=branch, kind="TestTenant", node_id=tenant_id) == inherit

        await run(
            db=db,
            branch=branch,
            query=UPDATE_TENANT,
            variables={"id": tenant_id, "name": "tenant-states", "metadata": {"owners": []}},
        )
        assert await read_ownership(db=db, branch=branch, kind="TestTenant", node_id=tenant_id) == {
            "state": "NO_OWNER",
            "origin": "SELF",
            "origin_node": {"id": tenant_id},
            "owners": [],
        }

        await run(
            db=db,
            branch=branch,
            query=UPDATE_TENANT,
            variables={"id": tenant_id, "name": "tenant-states", "metadata": {"owners": None}},
        )
        assert await read_ownership(db=db, branch=branch, kind="TestTenant", node_id=tenant_id) == inherit

    async def test_upsert_sets_owners_that_a_child_inherits_and_the_filters_find(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        data = await run(
            db=db,
            branch=branch,
            query="""
            mutation($group: String!) {
                TestTenantUpsert(data: {name: {value: "tenant-upsert"}, node_metadata: {owners: [{kind: "CoreAccountGroup", name: $group}]}}) {
                    object { id }
                }
            }
            """,
            variables={"group": "security"},
        )
        tenant_id = data["TestTenantUpsert"]["object"]["id"]
        data = await run(
            db=db,
            branch=branch,
            query="""
            mutation($tenant: String!) {
                TestRackCreate(data: {name: {value: "rack-upsert"}, tenant: {id: $tenant}}) { object { id } }
            }
            """,
            variables={"tenant": tenant_id},
        )
        rack_id = data["TestRackCreate"]["object"]["id"]

        assert await read_ownership(db=db, branch=branch, kind="TestRack", node_id=rack_id) == {
            "state": "INHERIT",
            "origin": "PARENT",
            "origin_node": {"id": tenant_id},
            "owners": own_owner(node_id=tenant_id, group_id=groups["security"], name="security")["owners"],
        }

        data = await run(
            db=db,
            branch=branch,
            query="""
            query($group: ID!, $rack: ID!) {
                owned: TestRack(node_metadata__owners__ids: [$group]) { count edges { node { id } } }
                without_owner: TestRack(node_metadata__owners__isnull: true, ids: [$rack]) { count }
            }
            """,
            variables={"group": groups["security"], "rack": rack_id},
        )
        assert data["owned"] == {"count": 1, "edges": [{"node": {"id": rack_id}}]}
        assert data["without_owner"] == {"count": 0}

    async def test_owner_change_on_a_branch_leaves_the_default_branch_unchanged(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        data = await run(
            db=db,
            branch=branch,
            query="""
            mutation($group: String!) {
                TestTenantCreate(data: {name: {value: "tenant-branch"}, node_metadata: {owners: [{id: $group}]}}) {
                    object { id }
                }
            }
            """,
            variables={"group": groups["dc-emea"]},
        )
        tenant_id = data["TestTenantCreate"]["object"]["id"]
        other_branch = await create_branch(branch_name="owner-input-branch", db=db)

        await run(
            db=db,
            branch=other_branch,
            query=UPDATE_TENANT,
            variables={"id": tenant_id, "name": "tenant-branch", "metadata": {"owners": [{"id": groups["security"]}]}},
        )

        assert await read_ownership(db=db, branch=other_branch, kind="TestTenant", node_id=tenant_id) == own_owner(
            node_id=tenant_id, group_id=groups["security"], name="security"
        )
        assert await read_ownership(db=db, branch=branch, kind="TestTenant", node_id=tenant_id) == own_owner(
            node_id=tenant_id, group_id=groups["dc-emea"], name="dc-emea"
        )

    async def test_create_with_an_owner_that_is_not_an_account_or_a_group_creates_nothing(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        other = await run(
            db=db,
            branch=branch,
            query='mutation { TestTenantCreate(data: {name: {value: "tenant-not-owner"}}) { object { id } } }',
        )
        result = await graphql_query(
            query="""
            mutation($owner: String!) {
                TestTenantCreate(data: {name: {value: "tenant-refused"}, node_metadata: {owners: [{id: $owner}]}}) {
                    ok
                }
            }
            """,
            db=db,
            branch=branch,
            variables={"owner": other["TestTenantCreate"]["object"]["id"]},
        )

        owner_id = other["TestTenantCreate"]["object"]["id"]
        assert [error.message for error in result.errors or []] == [
            f"Only an account or an account group can be an owner, not: {owner_id} at node_metadata.owners"
        ]
        assert (
            await NodeManager.query(
                db=db, schema="TestTenant", branch=branch, filters={"name__value": "tenant-refused"}
            )
            == []
        )
