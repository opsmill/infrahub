from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


TAG_METADATA_QUERY = """
query GetTag($id: ID!) {
    BuiltinTag(ids: [$id]) {
        edges {
            node_metadata {
                updated_at
                updated_by { id }
            }
            node {
                description {
                    value
                    updated_at
                    updated_by { id }
                }
            }
        }
    }
}
"""


async def _create_account(db: InfrahubDatabase, name: str) -> Node:
    account = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await account.new(db=db, name=name, account_type="User", password="accountPassword123")
    await account.save(db=db)
    return account


async def _query_tag(db: InfrahubDatabase, branch: Branch, tag_id: str, at: Timestamp | None = None) -> dict[str, Any]:
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch, at=at)
    result = await graphql(
        schema=gql_params.schema,
        source=TAG_METADATA_QUERY,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": tag_id},
    )
    assert result.errors is None
    assert result.data
    edges = result.data["BuiltinTag"]["edges"]
    assert len(edges) == 1
    return edges[0]


async def test_updated_metadata_at_past_time_on_default_branch(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A query at a past time returns the updated_at and updated_by of the value as of that time."""
    account_a = await _create_account(db=db, name="account-a")
    account_b = await _create_account(db=db, name="account-b")

    tag = await Node.init(db=db, schema=InfrahubKind.TAG)
    await tag.new(db=db, name="tag-history", description="two")
    await tag.save(db=db, user_id=account_a.id)

    state_after_a = await _query_tag(db=db, branch=default_branch, tag_id=tag.id)
    assert state_after_a["node"]["description"]["value"] == "two"
    assert state_after_a["node"]["description"]["updated_by"] == {"id": account_a.id}
    assert state_after_a["node_metadata"]["updated_by"] == {"id": account_a.id}
    time_between_updates = Timestamp()

    tag.get_attribute("description").value = "three"
    await tag.save(db=db, user_id=account_b.id)

    state_at_past_time = await _query_tag(db=db, branch=default_branch, tag_id=tag.id, at=time_between_updates)

    assert state_at_past_time == state_after_a
