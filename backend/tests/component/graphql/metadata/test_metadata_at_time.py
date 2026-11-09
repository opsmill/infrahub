from __future__ import annotations

from datetime import datetime
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


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


async def test_attribute_updated_metadata_at_past_time_includes_cleared_source(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Clearing an attribute's source counts as its latest update for a query at a later past time."""
    account_a = await _create_account(db=db, name="account-a")
    account_b = await _create_account(db=db, name="account-b")
    account_c = await _create_account(db=db, name="account-c")
    start = Timestamp()

    tag = await Node.init(db=db, schema=InfrahubKind.TAG)
    await tag.new(db=db, name="tag-source", description="one")
    tag.get_attribute("description").set_source(account_a.id)
    await tag.save(db=db, user_id=account_a.id, at=start.add(seconds=10))

    tag.get_attribute("description").clear_source()
    await tag.save(db=db, user_id=account_b.id, at=start.add(seconds=20))

    tag.get_attribute("description").value = "two"
    await tag.save(db=db, user_id=account_c.id, at=start.add(seconds=30))

    state = await _query_tag(db=db, branch=default_branch, tag_id=tag.id, at=start.add(seconds=25))

    description = state["node"]["description"]
    assert description["value"] == "one"
    assert description["updated_by"] == {"id": account_b.id}
    assert _parse_datetime(description["updated_at"]) == start.add(seconds=20).to_datetime()


async def test_node_updated_metadata_at_past_time_includes_removal_from_group(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Removing a node from a group counts as the node's latest update for a query at a later past time."""
    account_a = await _create_account(db=db, name="account-a")
    account_b = await _create_account(db=db, name="account-b")
    account_c = await _create_account(db=db, name="account-c")
    start = Timestamp().add(seconds=-100)

    tag = await Node.init(db=db, schema=InfrahubKind.TAG)
    await tag.new(db=db, name="tag-group", description="one")
    await tag.save(db=db, user_id=account_a.id, at=start.add(seconds=10))

    group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await group.new(db=db, name="group-history", members=[tag])
    await group.save(db=db, user_id=account_a.id, at=start.add(seconds=15))

    await group.get_relationship("members").update(db=db, data=[])
    await group.save(db=db, user_id=account_b.id, at=start.add(seconds=20))

    tag.get_attribute("description").value = "two"
    await tag.save(db=db, user_id=account_c.id, at=start.add(seconds=30))

    state = await _query_tag(db=db, branch=default_branch, tag_id=tag.id, at=start.add(seconds=25))

    node_metadata = state["node_metadata"]
    assert node_metadata["updated_by"] == {"id": account_b.id}
    assert _parse_datetime(node_metadata["updated_at"]) == start.add(seconds=20).to_datetime()


async def test_peers_ordered_by_updated_at_at_past_time(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Ordering peers by updated_at at a past time uses each peer's latest update as of that time."""
    account_a = await _create_account(db=db, name="account-a")
    start = Timestamp().add(seconds=-100)

    tag_one = await Node.init(db=db, schema=InfrahubKind.TAG)
    await tag_one.new(db=db, name="tag-one", description="one")
    await tag_one.save(db=db, user_id=account_a.id, at=start.add(seconds=10))

    tag_two = await Node.init(db=db, schema=InfrahubKind.TAG)
    await tag_two.new(db=db, name="tag-two", description="one")
    await tag_two.save(db=db, user_id=account_a.id, at=start.add(seconds=11))

    group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await group.new(db=db, name="group-order", members=[tag_one, tag_two])
    await group.save(db=db, user_id=account_a.id, at=start.add(seconds=15))

    tag_one.get_attribute("description").value = "two"
    await tag_one.save(db=db, user_id=account_a.id, at=start.add(seconds=20))

    tag_two.get_attribute("description").value = "two"
    await tag_two.save(db=db, user_id=account_a.id, at=start.add(seconds=30))

    query = """
    query GetGroup($id: ID!) {
        CoreStandardGroup(ids: [$id]) {
            edges {
                node {
                    members(order: {node_metadata: {updated_at: DESC}}) {
                        edges { node { id } }
                    }
                }
            }
        }
    }
    """
    default_branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=default_branch, at=start.add(seconds=25))
    result = await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values={"id": group.id},
    )

    assert result.errors is None
    assert result.data
    members = result.data["CoreStandardGroup"]["edges"][0]["node"]["members"]["edges"]
    assert [member["node"]["id"] for member in members] == [tag_one.id, tag_two.id]
