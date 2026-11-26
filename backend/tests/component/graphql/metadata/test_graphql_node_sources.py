from __future__ import annotations

from operator import itemgetter
from typing import TYPE_CHECKING, Any

import pytest
import ujson

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.core import registry
from infrahub.core.constants import GlobalPermissions, InfrahubKind, PermissionAction, PermissionDecision
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.api.dependencies import build_graphql_query_permission_checker
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql
from tests.helpers.ownership import SOURCES_FIELD, add_node, create, run
from tests.helpers.schema.ownership import OWNERSHIP_SCHEMA

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

SOURCE_FIELDS = "sources { id kind display_label hfid is_deleted }"

CREATE = """
mutation($name: String!, $metadata: NodeMetadataInput) {
    %(kind)sCreate(data: {name: {value: $name}, node_metadata: $metadata}) { object { id } }
}
"""

UPDATE_TENANT = """
mutation($id: String!, $metadata: NodeMetadataInput) {
    TestTenantUpdate(data: {id: $id, node_metadata: $metadata}) { ok }
}
"""

LIST = """
query($ids: [ID], $sources: [ID], $limit: Int) {
    %(kind)s(ids: $ids, node_metadata__sources__ids: $sources, limit: $limit) {
        count
        edges { node { id } node_metadata { ownership { state owners { id } } %(fields)s } }
    }
}
"""

CREATE_TAG_WITH_PROFILE = """
mutation($name: String!, $profile: String!) {
    BuiltinTagCreate(data: {name: {value: $name}, profiles: [{id: $profile}]}) {
        object { description { value is_from_profile source { id } } }
    }
}
"""


async def create_with_sources(
    db: InfrahubDatabase, branch: Branch, kind: str, name: str, sources: list[str] | None = None
) -> str:
    metadata = None if sources is None else {"sources": [{"id": source_id} for source_id in sources]}
    return await create(db=db, branch=branch, query=CREATE % {"kind": kind}, kind=kind, name=name, metadata=metadata)


async def list_nodes(
    db: InfrahubDatabase, branch: Branch, kind: str = "TestTenant", **variables: Any
) -> tuple[int, dict[str, dict[str, Any]]]:
    """Return the count of the list and the `node_metadata` of each node of the page, by node ID."""
    data = await run(db=db, branch=branch, query=LIST % {"kind": kind, "fields": SOURCE_FIELDS}, variables=variables)
    edges = data[kind]["edges"]
    return data[kind]["count"], {edge["node"]["id"]: edge["node_metadata"] for edge in edges}


async def read_sources(db: InfrahubDatabase, branch: Branch, node_id: str) -> list[dict[str, Any]]:
    _, nodes = await list_nodes(db=db, branch=branch, ids=[node_id])
    return nodes[node_id]["sources"]


async def as_source(db: InfrahubDatabase, node: Node) -> dict[str, Any]:
    """Return a node as the `sources` field reads it."""
    return {
        "id": node.id,
        "kind": node.get_kind(),
        "display_label": await node.get_display_label(db=db),
        "hfid": await node.get_hfid(db=db),
        "is_deleted": False,
    }


@pytest.fixture(scope="class")
async def sources(
    db: InfrahubDatabase, default_branch_scope_class: Branch, register_core_models_schema_scope_class: SchemaBranch
) -> dict[str, Node]:
    registry.schema.register_schema(schema=OWNERSHIP_SCHEMA, branch=default_branch_scope_class.name)
    default_branch_scope_class.update_schema_hash()
    return {
        "cmdb-sync": await add_node(db=db, kind=InfrahubKind.ACCOUNT, name="cmdb-sync", password="a-password"),
        "dc-emea": await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="dc-emea"),
        "infra-data": await add_node(
            db=db, kind=InfrahubKind.REPOSITORY, name="infra-data", location="git@example.com:infra-data.git"
        ),
        "tag-profile": await add_node(db=db, kind="ProfileBuiltinTag", profile_name="tag-profile", description="given"),
    }


def listed(*nodes: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(nodes, key=itemgetter("id"))


class TestNodeSources:
    async def test_source_filter_counts_all_matching_nodes_and_returns_one_page(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, sources: dict[str, Node]
    ) -> None:
        branch = default_branch_scope_class
        sync_id = sources["cmdb-sync"].id
        synced_ids = {
            await create_with_sources(db=db, branch=branch, kind="TestSite", name=f"site-{index}", sources=[sync_id])
            for index in range(12)
        }
        await create_with_sources(db=db, branch=branch, kind="TestSite", name="site-without-source")
        await create_with_sources(
            db=db, branch=branch, kind="TestSite", name="site-of-the-repository", sources=[sources["infra-data"].id]
        )

        count, page = await list_nodes(db=db, branch=branch, kind="TestSite", sources=[sync_id], limit=5)
        _, all_pages = await list_nodes(db=db, branch=branch, kind="TestSite", sources=[sync_id])

        assert count == 12
        assert len(page) == 5
        assert set(page) < synced_ids
        assert set(all_pages) == synced_ids

    async def test_node_with_two_sources_matches_the_filter_on_one_and_shows_both(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, sources: dict[str, Node]
    ) -> None:
        branch = default_branch_scope_class
        tenant_id = await create(
            db=db,
            branch=branch,
            query=CREATE % {"kind": "TestTenant"},
            kind="TestTenant",
            name="tenant-two-sources",
            metadata={
                "sources": [
                    {"kind": InfrahubKind.ACCOUNT, "hfid": ["cmdb-sync"]},
                    {"kind": InfrahubKind.REPOSITORY, "hfid": ["infra-data"]},
                ]
            },
        )
        other_id = await create_with_sources(
            db=db, branch=branch, kind="TestTenant", name="tenant-of-the-group", sources=[sources["dc-emea"].id]
        )

        _, by_repository = await list_nodes(
            db=db, branch=branch, ids=[tenant_id, other_id], sources=[sources["infra-data"].id]
        )

        assert list(by_repository) == [tenant_id]
        assert by_repository[tenant_id]["sources"] == listed(
            await as_source(db=db, node=sources["cmdb-sync"]), await as_source(db=db, node=sources["infra-data"])
        )

    async def test_sources_left_out_stay_and_null_or_empty_list_removes_them(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, sources: dict[str, Node]
    ) -> None:
        branch = default_branch_scope_class
        source_ids = [sources["cmdb-sync"].id, sources["infra-data"].id]
        tenant_ids = [
            await create_with_sources(db=db, branch=branch, kind="TestTenant", name=f"tenant-cleared-{index}")
            for index in (1, 2)
        ]
        references = [{"id": source_id} for source_id in source_ids]
        for tenant_id in tenant_ids:
            await run(
                db=db,
                branch=branch,
                query=UPDATE_TENANT,
                variables={"id": tenant_id, "metadata": {"sources": references}},
            )
        owners = {"owners": [{"id": sources["dc-emea"].id}]}

        await run(db=db, branch=branch, query=UPDATE_TENANT, variables={"id": tenant_ids[0], "metadata": owners})
        _, kept = await list_nodes(db=db, branch=branch, ids=[tenant_ids[0]])
        await run(
            db=db, branch=branch, query=UPDATE_TENANT, variables={"id": tenant_ids[0], "metadata": {"sources": None}}
        )
        await run(
            db=db, branch=branch, query=UPDATE_TENANT, variables={"id": tenant_ids[1], "metadata": {"sources": []}}
        )
        _, cleared = await list_nodes(db=db, branch=branch, ids=tenant_ids)

        assert [source["id"] for source in kept[tenant_ids[0]]["sources"]] == sorted(source_ids)
        assert [cleared[tenant_id]["sources"] for tenant_id in tenant_ids] == [[], []]
        # An empty list of sources gives the node no "no owner" state.
        assert cleared[tenant_ids[0]]["ownership"] == {"state": "OWNERS", "owners": owners["owners"]}
        assert cleared[tenant_ids[1]]["ownership"] == {"state": "INHERIT", "owners": []}

    async def test_attribute_set_by_a_profile_keeps_the_profile_as_source(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, sources: dict[str, Node]
    ) -> None:
        data = await run(
            db=db,
            branch=default_branch_scope_class,
            query=CREATE_TAG_WITH_PROFILE,
            variables={"name": "tag-with-profile", "profile": sources["tag-profile"].id},
        )

        assert data["BuiltinTagCreate"]["object"]["description"] == {
            "value": "given",
            "is_from_profile": True,
            "source": {"id": sources["tag-profile"].id},
        }

    async def test_deleted_source_stays_in_the_list_as_deleted(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, sources: dict[str, Node]
    ) -> None:
        branch = default_branch_scope_class
        group = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="team-to-delete")
        tenant_id = await create_with_sources(
            db=db, branch=branch, kind="TestTenant", name="tenant-of-a-deleted-source", sources=[group.id]
        )

        await group.delete(db=db)

        assert await read_sources(db=db, branch=branch, node_id=tenant_id) == [
            {"id": group.id, "kind": None, "display_label": None, "hfid": None, "is_deleted": True}
        ]


class TestNodeSourcesPermissions:
    @pytest.fixture(scope="class")
    async def session(
        self, db: InfrahubDatabase, sources: dict[str, Node], default_permission_backend_scope_class: None
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
        account = await add_node(db=db, kind=InfrahubKind.ACCOUNT, name="importer", password="a-password")
        await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="importers", roles=[role], members=[account])
        return AccountSession(authenticated=True, auth_type=AuthType.API, account_id=account.id)

    async def test_user_with_update_permission_changes_the_sources_and_the_event_records_both_values(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        sources: dict[str, Node],
        session: AccountSession,
    ) -> None:
        branch = default_branch_scope_class
        tenant_id = await create_with_sources(
            db=db, branch=branch, kind="TestTenant", name="tenant-changed-by-a-user", sources=[sources["cmdb-sync"].id]
        )
        new_ids = sorted([sources["infra-data"].id, sources["dc-emea"].id])
        variables = {"id": tenant_id, "metadata": {"sources": [{"id": source_id} for source_id in new_ids]}}
        event_service = MemoryInfrahubEvent()
        service = await InfrahubServices.new(event=event_service, workflow=WorkflowLocalExecution())
        gql_params = await prepare_graphql_params(db=db, branch=branch, service=service, account_session=session)

        await build_graphql_query_permission_checker().check(
            db=db,
            account_session=session,
            analyzed_query=InfrahubGraphQLQueryAnalyzer(
                query=UPDATE_TENANT,
                query_variables=variables,
                schema=gql_params.schema,
                branch=branch,
                schema_branch=registry.schema.get_schema_branch(name=branch.name),
            ),
            query_parameters=gql_params,
            branch=branch,
        )
        result = await graphql(
            schema=gql_params.schema,
            source=UPDATE_TENANT,
            context_value=gql_params.context,
            variable_values=variables,
        )
        assert result.errors is None, result.errors
        assert gql_params.context.background
        await gql_params.context.background()

        assert [source["id"] for source in await read_sources(db=db, branch=branch, node_id=tenant_id)] == new_ids
        assert len(event_service.events) == 1
        change = event_service.events[0].changelog.attributes[SOURCES_FIELD]
        assert (change.value, change.value_previous) == (
            ujson.dumps(new_ids),
            ujson.dumps([sources["cmdb-sync"].id]),
        )
