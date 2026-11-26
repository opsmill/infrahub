from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from tests.helpers.graphql import graphql_query
from tests.helpers.ownership import create, create_groups, from_node, own, read_node, run
from tests.helpers.schema.ownership import OWNERSHIP_SCHEMA

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

OWNERSHIP = "ownership { state origin origin_node { id } owners { id } }"

CREATE_SITE = """
mutation($name: String!, $parent: String, $metadata: NodeMetadataInput) {
    TestSiteCreate(data: {name: {value: $name}, parent: {id: $parent}, node_metadata: $metadata}) { object { id } }
}
"""

CREATE_TOP_SITE = """
mutation($name: String!, $metadata: NodeMetadataInput) {
    TestSiteCreate(data: {name: {value: $name}, node_metadata: $metadata}) { object { id } }
}
"""

UPDATE_SITE = """
mutation($id: String!, $metadata: NodeMetadataInput) {
    TestSiteUpdate(data: {id: $id, node_metadata: $metadata}) { ok }
}
"""

READ_SITE = """
query($ids: [ID]) {
    TestSite(ids: $ids) {
        edges {
            node {
                name { value %(ownership)s }
                parent { %(ownership)s }
                children { count %(ownership)s edges { %(ownership)s node { id } } }
            }
        }
    }
}
""" % {"ownership": OWNERSHIP}

READ_PARENT_OWNERSHIP_ONLY = """
query($ids: [ID]) {
    TestSite(ids: $ids) { edges { node { parent { %(ownership)s } } } }
}
""" % {"ownership": OWNERSHIP}

CREATE_TENANT = """
mutation($name: String!, $owners: [MetadataNodeInput!]) {
    TestTenantCreate(data: {name: {value: $name, owners: $owners}}) { object { id } }
}
"""

UPDATE_TENANT_NAME = """
mutation($id: String!, $name: TextAttributeUpdate) {
    TestTenantUpdate(data: {id: $id, name: $name}) { ok }
}
"""

READ_TENANT = """
query($ids: [ID]) {
    TestTenant(ids: $ids) { edges { node { name { value owner { id } %(ownership)s } } } }
}
""" % {"ownership": OWNERSHIP}

CREATE_PROFILE = """
mutation($name: String!, $metadata: NodeMetadataInput) {
    ProfileTestTenantCreate(data: {profile_name: {value: $name}, node_metadata: $metadata}) { object { id } }
}
"""

READ_PROFILE = """
query($ids: [ID], $fields: [String!]) {
    ProfileTestTenant(ids: $ids) {
        edges { node_metadata { target_field_ownership(fields: $fields) { field %(ownership)s } } }
    }
}
""" % {"ownership": OWNERSHIP}

CREATE_TENANT_WITH_PROFILE = """
mutation($name: String!, $profile: String!) {
    TestTenantCreate(data: {name: {value: $name}, profiles: [{id: $profile}]}) { object { id } }
}
"""

READ_OWNER_DEPRECATION = """
query {
    __type(name: "TextAttribute") { fields(includeDeprecated: true) { name isDeprecated } }
}
"""


class TestFieldOwnerInputs:
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

    async def test_relationship_fields_return_their_owners_with_and_without_peers(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        top_id = await create(
            db,
            branch,
            CREATE_TOP_SITE,
            "TestSite",
            name="site-top",
            metadata={
                "owners": [{"id": groups["dc-emea"]}],
                "field_owners": [
                    {"field": "parent", "owners": [{"id": groups["network-emea"]}]},
                    {"field": "children", "owners": [{"id": groups["security"]}, {"id": groups["network-emea"]}]},
                ],
            },
        )
        child_ids = [
            await create(db, branch, CREATE_SITE, "TestSite", name=name, parent=top_id)
            for name in ("site-child-a", "site-child-b")
        ]

        top = await read_node(db=db, branch=branch, query=READ_SITE, kind="TestSite", node_id=top_id)
        child = await read_node(db=db, branch=branch, query=READ_SITE, kind="TestSite", node_id=child_ids[0])
        parent_only = await read_node(
            db=db, branch=branch, query=READ_PARENT_OWNERSHIP_ONLY, kind="TestSite", node_id=child_ids[0]
        )

        children_owners = own(top_id, groups["security"], groups["network-emea"])
        assert top["name"] == {"value": "site-top", "ownership": from_node(top_id, groups["dc-emea"])}
        assert top["parent"] == {"ownership": own(top_id, groups["network-emea"])}
        assert top["children"]["count"] == 2
        assert top["children"]["ownership"] == children_owners
        assert sorted(edge["node"]["id"] for edge in top["children"]["edges"]) == sorted(child_ids)
        assert [edge["ownership"] for edge in top["children"]["edges"]] == [children_owners, children_owners]
        assert child["parent"] == {"ownership": from_node(child_ids[0], groups["dc-emea"])}
        assert child["children"] == {"count": 0, "ownership": from_node(child_ids[0], groups["dc-emea"]), "edges": []}
        assert parent_only == {"parent": {"ownership": from_node(child_ids[0], groups["dc-emea"])}}

    async def test_field_owners_with_an_unknown_field_is_refused_and_changes_nothing(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        site_id = await create(
            db,
            branch,
            CREATE_TOP_SITE,
            "TestSite",
            name="site-refused",
            metadata={"owners": [{"id": groups["dc-emea"]}]},
        )

        result = await graphql_query(
            query=UPDATE_SITE,
            db=db,
            branch=branch,
            variables={
                "id": site_id,
                "metadata": {
                    "owners": [{"id": groups["security"]}],
                    "field_owners": [
                        {"field": "parent", "owners": []},
                        {"field": "unknown", "owners": [{"id": groups["security"]}]},
                    ],
                },
            },
        )

        assert [error.message for error in result.errors or []] == [
            "unknown is not an attribute or a relationship of TestSite at node_metadata.field_owners"
        ]
        site = await read_node(db=db, branch=branch, query=READ_SITE, kind="TestSite", node_id=site_id)
        assert site["name"]["ownership"] == from_node(site_id, groups["dc-emea"])
        assert site["parent"] == {"ownership": from_node(site_id, groups["dc-emea"])}

    async def test_field_owners_entry_without_owners_changes_nothing(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        site_id = await create(
            db,
            branch,
            CREATE_TOP_SITE,
            "TestSite",
            name="site-entry-without-owners",
            metadata={"field_owners": [{"field": "parent", "owners": [{"id": groups["network-emea"]}]}]},
        )

        await run(
            db=db,
            branch=branch,
            query=UPDATE_SITE,
            variables={"id": site_id, "metadata": {"field_owners": [{"field": "parent"}]}},
        )

        site = await read_node(db=db, branch=branch, query=READ_SITE, kind="TestSite", node_id=site_id)
        assert site["parent"] == {"ownership": own(site_id, groups["network-emea"])}

    async def test_owners_next_to_the_value_set_own_owners_no_owner_and_inherit(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        tenant_id = await create(
            db,
            branch,
            CREATE_TENANT,
            "TestTenant",
            name="tenant-owners",
            owners=[{"kind": "CoreAccountGroup", "name": "dc-emea"}, {"id": groups["network-emea"]}],
        )

        created = await read_node(db=db, branch=branch, query=READ_TENANT, kind="TestTenant", node_id=tenant_id)

        assert created["name"] == {
            "value": "tenant-owners",
            "owner": None,
            "ownership": own(tenant_id, groups["dc-emea"], groups["network-emea"]),
        }

        await run(
            db=db,
            branch=branch,
            query=UPDATE_TENANT_NAME,
            variables={"id": tenant_id, "name": {"value": "tenant-renamed", "owners": [{"id": groups["security"]}]}},
        )
        renamed = await read_node(db=db, branch=branch, query=READ_TENANT, kind="TestTenant", node_id=tenant_id)
        await run(db=db, branch=branch, query=UPDATE_TENANT_NAME, variables={"id": tenant_id, "name": {"owners": []}})
        no_owner = await read_node(db=db, branch=branch, query=READ_TENANT, kind="TestTenant", node_id=tenant_id)
        await run(db=db, branch=branch, query=UPDATE_TENANT_NAME, variables={"id": tenant_id, "name": {"owners": None}})
        inherit = await read_node(db=db, branch=branch, query=READ_TENANT, kind="TestTenant", node_id=tenant_id)

        assert renamed["name"] == {
            "value": "tenant-renamed",
            "owner": {"id": groups["security"]},
            "ownership": own(tenant_id, groups["security"]),
        }
        assert no_owner["name"] == {"value": "tenant-renamed", "owner": None, "ownership": own(tenant_id)}
        assert inherit["name"] == {
            "value": "tenant-renamed",
            "owner": None,
            "ownership": {"state": "INHERIT", "origin": None, "origin_node": None, "owners": []},
        }

    async def test_deprecated_owner_gives_the_one_own_owner_and_a_write_replaces_the_own_owners(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        branch = default_branch_scope_class
        tenant_id = await create(
            db,
            branch,
            CREATE_TENANT,
            "TestTenant",
            name="tenant-owner",
            owners=[{"id": groups["dc-emea"]}, {"id": groups["network-emea"]}],
        )

        two_owners = await read_node(db=db, branch=branch, query=READ_TENANT, kind="TestTenant", node_id=tenant_id)
        await run(db=db, branch=branch, query=UPDATE_TENANT_NAME, variables={"id": tenant_id, "name": {"owner": None}})
        after_null = await read_node(db=db, branch=branch, query=READ_TENANT, kind="TestTenant", node_id=tenant_id)
        await run(
            db=db,
            branch=branch,
            query=UPDATE_TENANT_NAME,
            variables={"id": tenant_id, "name": {"owner": groups["security"]}},
        )
        one_owner = await read_node(db=db, branch=branch, query=READ_TENANT, kind="TestTenant", node_id=tenant_id)
        await run(db=db, branch=branch, query=UPDATE_TENANT_NAME, variables={"id": tenant_id, "name": {"owner": None}})
        one_after_null = await read_node(db=db, branch=branch, query=READ_TENANT, kind="TestTenant", node_id=tenant_id)
        await run(db=db, branch=branch, query=UPDATE_TENANT_NAME, variables={"id": tenant_id, "name": {"owners": []}})
        zero_owners = await read_node(db=db, branch=branch, query=READ_TENANT, kind="TestTenant", node_id=tenant_id)

        two = own(tenant_id, groups["dc-emea"], groups["network-emea"])
        assert two_owners["name"] == {"value": "tenant-owner", "owner": None, "ownership": two}
        assert after_null["name"] == {"value": "tenant-owner", "owner": None, "ownership": two}
        one = {
            "value": "tenant-owner",
            "owner": {"id": groups["security"]},
            "ownership": own(tenant_id, groups["security"]),
        }
        assert one_owner["name"] == one
        assert one_after_null["name"] == one
        assert zero_owners["name"] == {"value": "tenant-owner", "owner": None, "ownership": own(tenant_id)}

    async def test_profile_gives_owners_to_one_field_of_its_nodes(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        groups: dict[str, str],
        session_admin_scope_class: AccountSession,
    ) -> None:
        branch = default_branch_scope_class
        profile_id = await create(
            db,
            branch,
            CREATE_PROFILE,
            "ProfileTestTenant",
            session=session_admin_scope_class,
            name="profile-field",
            metadata={"target_field_owners": [{"field": "name", "owners": [{"id": groups["network-emea"]}]}]},
        )
        tenant_id = await create(
            db,
            branch,
            CREATE_TENANT_WITH_PROFILE,
            "TestTenant",
            session=session_admin_scope_class,
            name="tenant-of-profile",
            profile=profile_id,
        )

        profile = await run(
            db=db, branch=branch, query=READ_PROFILE, variables={"ids": [profile_id], "fields": ["name"]}
        )
        tenant = await read_node(db=db, branch=branch, query=READ_TENANT, kind="TestTenant", node_id=tenant_id)

        assert profile["ProfileTestTenant"]["edges"] == [
            {
                "node_metadata": {
                    "target_field_ownership": [{"field": "name", "ownership": own(profile_id, groups["network-emea"])}]
                }
            }
        ]
        assert tenant["name"]["ownership"] == {
            "state": "INHERIT",
            "origin": "PROFILE",
            "origin_node": {"id": profile_id},
            "owners": [{"id": groups["network-emea"]}],
        }

    async def test_target_field_ownership_refuses_an_unknown_field(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        groups: dict[str, str],
        session_admin_scope_class: AccountSession,
    ) -> None:
        branch = default_branch_scope_class
        profile_id = await create(
            db,
            branch,
            CREATE_PROFILE,
            "ProfileTestTenant",
            session=session_admin_scope_class,
            name="profile-unknown-field",
            metadata={"target_field_owners": [{"field": "name", "owners": [{"id": groups["network-emea"]}]}]},
        )

        result = await graphql_query(
            query=READ_PROFILE, db=db, branch=branch, variables={"ids": [profile_id], "fields": ["name", "unknown"]}
        )

        assert [error.message for error in result.errors or []] == [
            "unknown is not an attribute or a relationship of TestTenant at target_field_ownership.fields"
        ]

    async def test_attribute_owner_and_is_protected_fields_are_deprecated(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, groups: dict[str, str]
    ) -> None:
        data = await run(db=db, branch=default_branch_scope_class, query=READ_OWNER_DEPRECATION)

        assert {field["name"] for field in data["__type"]["fields"] if field["isDeprecated"]} == {
            "is_protected",
            "owner",
        }
