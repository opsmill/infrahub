"""Helpers for the diff, merge and rebase tests of node owners."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.branch.tasks import rebase_branch
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.workers.dependencies import build_database
from tests.helpers.dependency_override import override_dependency
from tests.helpers.ownership import OWNERS_FIELD, OwnerDataset

from ..get_one_node import get_one_diff_node
from .conftest import get_diff_coordinator, get_diff_merger

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffProperty, EnrichedDiffRoot
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.database import InfrahubDatabase

OWNER_EDGE_TYPES = ("HAS_OWNER", "HAS_NO_OWNER", "HAS_SOURCE")


async def update_diff(
    db: InfrahubDatabase, default_branch: Branch, branch: Branch, diff_repository: DiffRepository
) -> EnrichedDiffRoot:
    coordinator = await get_diff_coordinator(db=db, branch=branch)
    metadata = await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    return await diff_repository.get_one(diff_branch_name=branch.name, diff_id=metadata.uuid)


async def merge(db: InfrahubDatabase, branch: Branch, at: Timestamp | None = None) -> None:
    """Merge the branch with its latest diff, the way the merge of a branch does after the diff update."""
    merger = await get_diff_merger(db=db, branch=branch)
    await merger.merge_graph(at=at or Timestamp())


async def rebase_with_conflict_check(
    db: InfrahubDatabase, default_branch: Branch, branch: Branch, dependency_provider: Provider
) -> None:
    """Rebase the branch the way a user does, with the check that refuses some conflicts."""
    context = InfrahubContext.init(
        branch=default_branch, account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE)
    )
    with override_dependency(build_database, lambda singleton=True: db, dependency_provider=dependency_provider):  # noqa: ARG005
        await rebase_branch(branch=branch.name, context=context)


def owner_property(
    diff: EnrichedDiffRoot,
    node_id: str,
    field_name: str = OWNERS_FIELD,
    property_type: DatabaseEdgeType = DatabaseEdgeType.HAS_OWNER,
) -> EnrichedDiffProperty:
    node = get_one_diff_node(diff_root=diff, node_uuid=node_id)
    return node.get_attribute(name=field_name).get_property(property_type=property_type)


def has_owner_change(diff: EnrichedDiffRoot) -> bool:
    return any(attribute.name == OWNERS_FIELD for node in diff.nodes for attribute in node.attributes)


async def profile_with_device(db: InfrahubDatabase, dataset: OwnerDataset) -> tuple[str, str]:
    """Create a device profile and a device of the rack `rack-a` that uses it, and return their IDs."""
    profile = await Node.init(db=db, schema="ProfileTestDevice")
    await profile.new(db=db, profile_name="emea-fabric")
    await profile.save(db=db)
    device = await Node.init(db=db, schema="TestDevice")
    await device.new(db=db, name="device-with-profile", rack=dataset.ids["rack-a"], profiles=[profile])
    await device.save(db=db)
    return profile.id, device.id


async def holder_edges(
    db: InfrahubDatabase, branch: Branch, node_id: str
) -> list[tuple[str, str, str, str, str | None]]:
    """Return the type, the status, the peer, `from` and `to` of each edge of each holder of the node on one branch."""
    query = """
    MATCH (n:Node {uuid: $node_id})
    CALL (n) {
        MATCH (n)-[r:HAS_OWNER|HAS_NO_OWNER|HAS_SOURCE|HAS_OWNER_SOURCE|HAS_OWNER_SET|HAS_TARGET_OWNER_SET]->(peer)
        RETURN r, peer
        UNION ALL
        MATCH (n)-[:HAS_ATTRIBUTE]->(:Attribute)-[r:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SOURCE]->(peer)
        RETURN r, peer
        UNION ALL
        MATCH (n)-[:HAS_OWNER_SET|HAS_TARGET_OWNER_SET]->(:OwnerSet)-[r:HAS_OWNER|HAS_NO_OWNER|HAS_OWNER_SOURCE]->(peer)
        RETURN DISTINCT r, peer
        UNION ALL
        MATCH (n)-[:IS_RELATED]-(:Relationship)-[r:HAS_OWNER]->(peer)
        RETURN DISTINCT r, peer
    }
    WITH DISTINCT r, peer
    WHERE r.branch = $branch_name
    RETURN type(r) AS edge_type, r.status AS status, elementId(peer) AS peer_id, r.from AS from_time, r.to AS to_time
    ORDER BY edge_type, from_time, peer_id, status
    """
    results = await db.execute_query(query=query, params={"node_id": node_id, "branch_name": branch.name})
    return [(row["edge_type"], row["status"], row["peer_id"], row["from_time"], row["to_time"]) for row in results]


async def count_active_holder_edges(db: InfrahubDatabase, branch: Branch, node_id: str) -> int:
    edges = await holder_edges(db=db, branch=branch, node_id=node_id)
    return sum(1 for edge in edges if edge[0] in OWNER_EDGE_TYPES and edge[1] == "active" and edge[4] is None)
