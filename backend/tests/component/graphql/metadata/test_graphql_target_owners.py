from __future__ import annotations

from operator import itemgetter
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.helpers.graphql import graphql_query
from tests.helpers.ownership import create_groups
from tests.helpers.schema.ownership import OWNERSHIP_SCHEMA

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

TENANT_PROFILE = "ProfileTestTenant"
SITE_TEMPLATE = "TemplateTestSite"

OWNERSHIP_FIELDS = "state origin origin_node { id } owners { id kind display_label hfid is_deleted }"

READ_METADATA = """
query($ids: [ID]) {
    %(kind)s(ids: $ids) {
        edges { node_metadata { ownership { %(fields)s } target_ownership { %(fields)s } } }
    }
}
"""

CREATE_PROFILE = """
mutation($name: String!, $metadata: NodeMetadataInput) {
    ProfileTestTenantCreate(data: {profile_name: {value: $name}, node_metadata: $metadata}) { object { id } }
}
"""

UPDATE_PROFILE = """
mutation($id: String!, $name: String!, $metadata: NodeMetadataInput) {
    ProfileTestTenantUpdate(data: {id: $id, profile_name: {value: $name}, node_metadata: $metadata}) { ok }
}
"""

CREATE_TENANT_WITH_PROFILE = """
mutation($name: String!, $profile: String!) {
    TestTenantCreate(data: {name: {value: $name}, profiles: [{id: $profile}]}) { object { id } }
}
"""

CREATE_TEMPLATE = """
mutation($name: String!, $metadata: NodeMetadataInput) {
    TemplateTestSiteCreate(data: {template_name: {value: $name}, node_metadata: $metadata}) { object { id } }
}
"""

CREATE_SITE_FROM_TEMPLATE = """
mutation($name: String!, $template: String!) {
    TestSiteCreate(data: {name: {value: $name}, object_template: {id: $template}}) { object { id } }
}
"""


async def run(
    db: InfrahubDatabase, branch: Branch, query: str, variables: dict[str, Any], session: AccountSession | None = None
) -> dict[str, Any]:
    # The mutations of a profile start a workflow for the account of the request.
    service = await InfrahubServices.new(workflow=WorkflowLocalExecution())
    result = await graphql_query(
        query=query, db=db, branch=branch, variables=variables, service=service, account_session=session
    )
    assert result.errors is None, result.errors
    assert result.data
    return result.data


async def create(
    db: InfrahubDatabase, branch: Branch, session: AccountSession, query: str, kind: str, **variables: Any
) -> str:
    data = await run(db=db, branch=branch, query=query, variables=variables, session=session)
    return data[f"{kind}Create"]["object"]["id"]


async def read_metadata(db: InfrahubDatabase, branch: Branch, kind: str, node_id: str) -> dict[str, Any]:
    data = await run(
        db=db,
        branch=branch,
        query=READ_METADATA % {"kind": kind, "fields": OWNERSHIP_FIELDS},
        variables={"ids": [node_id]},
    )
    edges = data[kind]["edges"]
    assert len(edges) == 1
    return edges[0]["node_metadata"]


def group_owners(groups: dict[str, str], *names: str) -> list[dict[str, Any]]:
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


def gives(holder_id: str, owners: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "state": "OWNERS" if owners else "NO_OWNER",
        "origin": "SELF",
        "origin_node": {"id": holder_id},
        "owners": owners,
    }


NOTHING = {"state": "INHERIT", "origin": None, "origin_node": None, "owners": []}


class TestTargetOwners:
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

    async def test_profile_gives_its_owners_to_its_nodes_apart_from_its_own_owners(
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
            session_admin_scope_class,
            CREATE_PROFILE,
            TENANT_PROFILE,
            name="profile-gives",
            metadata={
                "owners": [{"id": groups["security"]}],
                "target_owners": [{"kind": "CoreAccountGroup", "name": "dc-emea"}],
            },
        )
        tenant_id = await create(
            db,
            branch,
            session_admin_scope_class,
            CREATE_TENANT_WITH_PROFILE,
            "TestTenant",
            name="tenant-of-profile",
            profile=profile_id,
        )

        assert await read_metadata(db=db, branch=branch, kind=TENANT_PROFILE, node_id=profile_id) == {
            "ownership": gives(holder_id=profile_id, owners=group_owners(groups, "security")),
            "target_ownership": gives(holder_id=profile_id, owners=group_owners(groups, "dc-emea")),
        }
        assert await read_metadata(db=db, branch=branch, kind="TestTenant", node_id=tenant_id) == {
            "ownership": {
                "state": "INHERIT",
                "origin": "PROFILE",
                "origin_node": {"id": profile_id},
                "owners": group_owners(groups, "dc-emea"),
            },
            "target_ownership": None,
        }

        await run(
            db=db,
            branch=branch,
            query=UPDATE_PROFILE,
            session=session_admin_scope_class,
            variables={"id": profile_id, "name": "profile-renamed", "metadata": {"owners": []}},
        )

        assert await read_metadata(db=db, branch=branch, kind=TENANT_PROFILE, node_id=profile_id) == {
            "ownership": gives(holder_id=profile_id, owners=[]),
            "target_ownership": gives(holder_id=profile_id, owners=group_owners(groups, "dc-emea")),
        }

    async def test_template_gives_its_owners_to_the_nodes_created_from_it(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        groups: dict[str, str],
        session_admin_scope_class: AccountSession,
    ) -> None:
        branch = default_branch_scope_class
        template_id = await create(
            db,
            branch,
            session_admin_scope_class,
            CREATE_TEMPLATE,
            SITE_TEMPLATE,
            name="template-gives",
            metadata={"target_owners": [{"id": groups["dc-emea"]}, {"id": groups["network-emea"]}]},
        )
        site_id = await create(
            db,
            branch,
            session_admin_scope_class,
            CREATE_SITE_FROM_TEMPLATE,
            "TestSite",
            name="site-of-template",
            template=template_id,
        )

        assert await read_metadata(db=db, branch=branch, kind=SITE_TEMPLATE, node_id=template_id) == {
            "ownership": NOTHING,
            "target_ownership": gives(holder_id=template_id, owners=group_owners(groups, "dc-emea", "network-emea")),
        }
        assert (await read_metadata(db=db, branch=branch, kind="TestSite", node_id=site_id))["ownership"] == {
            "state": "INHERIT",
            "origin": "TEMPLATE",
            "origin_node": {"id": template_id},
            "owners": group_owners(groups, "dc-emea", "network-emea"),
        }

    async def test_empty_list_gives_no_owner_and_null_gives_nothing(
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
            session_admin_scope_class,
            CREATE_PROFILE,
            TENANT_PROFILE,
            name="profile-states",
            metadata={"target_owners": [{"id": groups["dc-emea"]}]},
        )
        tenant_id = await create(
            db,
            branch,
            session_admin_scope_class,
            CREATE_TENANT_WITH_PROFILE,
            "TestTenant",
            name="tenant-of-states",
            profile=profile_id,
        )

        await run(
            db=db,
            branch=branch,
            query=UPDATE_PROFILE,
            session=session_admin_scope_class,
            variables={"id": profile_id, "name": "profile-states", "metadata": {"target_owners": []}},
        )

        assert (await read_metadata(db=db, branch=branch, kind=TENANT_PROFILE, node_id=profile_id))[
            "target_ownership"
        ] == gives(holder_id=profile_id, owners=[])
        assert (await read_metadata(db=db, branch=branch, kind="TestTenant", node_id=tenant_id))["ownership"] == {
            "state": "INHERIT",
            "origin": "PROFILE",
            "origin_node": {"id": profile_id},
            "owners": [],
        }

        await run(
            db=db,
            branch=branch,
            query=UPDATE_PROFILE,
            session=session_admin_scope_class,
            variables={"id": profile_id, "name": "profile-states", "metadata": {"target_owners": None}},
        )

        assert (await read_metadata(db=db, branch=branch, kind=TENANT_PROFILE, node_id=profile_id))[
            "target_ownership"
        ] == NOTHING
        assert (await read_metadata(db=db, branch=branch, kind="TestTenant", node_id=tenant_id))["ownership"] == NOTHING

    async def test_target_owners_on_a_kind_that_is_not_a_profile_or_a_template_changes_nothing(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        groups: dict[str, str],
        session_admin_scope_class: AccountSession,
    ) -> None:
        branch = default_branch_scope_class
        tenant_id = await create(
            db,
            branch,
            session_admin_scope_class,
            """
            mutation($owner: String!) {
                TestTenantCreate(data: {name: {value: "tenant-before"}, node_metadata: {owners: [{id: $owner}]}}) {
                    object { id }
                }
            }
            """,
            "TestTenant",
            owner=groups["dc-emea"],
        )

        update = await graphql_query(
            query="""
            mutation($id: String!, $owner: String!) {
                TestTenantUpdate(
                    data: {
                        id: $id
                        name: {value: "tenant-after"}
                        node_metadata: {owners: [], target_owners: [{id: $owner}]}
                    }
                ) { ok }
            }
            """,
            db=db,
            branch=branch,
            variables={"id": tenant_id, "owner": groups["security"]},
        )
        create_result = await graphql_query(
            query="""
            mutation($owner: String!) {
                TestTenantCreate(
                    data: {name: {value: "tenant-refused"}, node_metadata: {target_owners: [{id: $owner}]}}
                ) { ok }
            }
            """,
            db=db,
            branch=branch,
            variables={"owner": groups["security"]},
        )

        refusal = "Only a profile or an object template gives owners to its nodes, not: TestTenant"
        assert [error.message for error in update.errors or []] == [f"{refusal} at node_metadata.target_owners"]
        assert [error.message for error in create_result.errors or []] == [f"{refusal} at node_metadata.target_owners"]
        stored = await NodeManager.get_one(db=db, branch=branch, id=tenant_id, raise_on_error=True)
        assert stored.name.value == "tenant-before"
        assert await read_metadata(db=db, branch=branch, kind="TestTenant", node_id=tenant_id) == {
            "ownership": gives(holder_id=tenant_id, owners=group_owners(groups, "dc-emea")),
            "target_ownership": None,
        }
        assert (
            await NodeManager.query(
                db=db, schema="TestTenant", branch=branch, filters={"name__value": "tenant-refused"}
            )
            == []
        )
