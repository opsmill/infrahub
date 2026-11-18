"""Data set and helpers for the diff, merge and rebase tests of node owners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import ujson

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.ownership.models import NODE_HOLDER, HolderKey, ResolvedOwnership, StoredOwnerState
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.ownership.resolver import OwnershipResolver
from infrahub.core.ownership.writer import OwnershipWriter
from infrahub.core.timestamp import Timestamp
from tests.helpers.schema.ownership import OWNERSHIP_SCHEMA

from ..get_one_node import get_one_diff_node
from .conftest import get_diff_coordinator, get_diff_merger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffProperty, EnrichedDiffRoot
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.database import InfrahubDatabase

USER_ID = "test-user-id"
OWNERS_FIELD = "node_metadata__owners"
TARGET_OWNERS_FIELD = "node_metadata__target_owners"
GROUP_NAMES = ("dc-emea", "network-emea", "security")


@dataclass
class OwnerDataset:
    """The tenant `tenant-a` holds the racks `rack-a` and `rack-b`, and `rack-a` holds the device `device-a`."""

    ids: dict[str, str]
    """The ID of each account group and each node, by name."""

    def owners(self, names: tuple[str, ...] | None) -> tuple[str, ...] | None:
        """Return the sorted IDs of account groups, with None for inherit and an empty tuple for "no owner"."""
        return None if names is None else tuple(sorted(self.ids[name] for name in names))

    def owner_list(self, names: tuple[str, ...] | None) -> str | None:
        """Return the value that the diff gives to these owners."""
        owner_ids = self.owners(names)
        return None if owner_ids is None else ujson.dumps(list(owner_ids))

    def owner_labels(self, names: tuple[str, ...], deleted: tuple[str, ...] = ()) -> str:
        """Return the label that the diff gives to these owners, with the mark of each deleted owner."""
        by_id = sorted(names, key=lambda name: self.ids[name])
        return ", ".join("deleted owner" if name in deleted else name for name in by_id)


async def _create(db: InfrahubDatabase, kind: str, name: str, **kwargs: Node) -> Node:
    node = await Node.init(db=db, schema=kind)
    await node.new(db=db, name=name, **kwargs)
    await node.save(db=db)
    return node


async def load_owner_dataset(db: InfrahubDatabase, default_branch: Branch) -> OwnerDataset:
    registry.schema.register_schema(schema=OWNERSHIP_SCHEMA, branch=default_branch.name)
    nodes = {name: await _create(db=db, kind=InfrahubKind.ACCOUNTGROUP, name=name) for name in GROUP_NAMES}
    nodes["tenant-a"] = await _create(db=db, kind="TestTenant", name="tenant-a")
    for name in ("rack-a", "rack-b"):
        nodes[name] = await _create(db=db, kind="TestRack", name=name, tenant=nodes["tenant-a"])
    nodes["device-a"] = await _create(db=db, kind="TestDevice", name="device-a", rack=nodes["rack-a"])
    return OwnerDataset(ids={name: node.id for name, node in nodes.items()})


async def set_owners(
    db: InfrahubDatabase,
    branch: Branch,
    node_id: str,
    owner_ids: tuple[str, ...] | None,
    holder: HolderKey = NODE_HOLDER,
) -> None:
    node = await NodeManager.get_one(db=db, branch=branch, id=node_id, raise_on_error=True)
    writer = OwnershipWriter(repository=OwnershipRepository(db=db, branch=branch, at=None))
    await writer.apply(
        node=node, holder=holder, state=StoredOwnerState(owner_ids=owner_ids), at=Timestamp(), user_id=USER_ID
    )


async def read_owners(
    db: InfrahubDatabase, branch: Branch, node_id: str, holder: HolderKey = NODE_HOLDER
) -> tuple[str, ...] | None:
    """Return the owners that one holder of the node stores, as the branch reads them."""
    stored = await OwnershipRepository(db=db, branch=branch, at=None).read(node_ids=[node_id], attributes=True)
    return stored[node_id].get(holder).owner_ids


async def resolve_owners(db: InfrahubDatabase, branch: Branch, node_id: str) -> ResolvedOwnership:
    """Return the owners that apply to the node, own or inherited, as the branch reads them."""
    resolver = OwnershipResolver(repository=OwnershipRepository(db=db, branch=branch, at=None))
    return (await resolver.resolve(node_ids=[node_id]))[node_id]


async def count_active_owner_edges(db: InfrahubDatabase, branch: Branch, node_id: str) -> int:
    """Count the open owner edges that the node vertex holds on one branch."""
    query = """
    MATCH (n:Node {uuid: $node_id})-[r:HAS_OWNER|HAS_NO_OWNER]->()
    WHERE r.branch = $branch_name AND r.status = "active" AND r.to IS NULL
    RETURN count(r) AS total
    """
    results = await db.execute_query(query=query, params={"node_id": node_id, "branch_name": branch.name})
    return results[0]["total"]


async def owner_edges(db: InfrahubDatabase, node_id: str) -> list[tuple[str, str, str, str, str | None]]:
    """Return the branch, the status, the peer, `from` and `to` of each owner edge of the node vertex."""
    query = """
    MATCH (n:Node {uuid: $node_id})-[r:HAS_OWNER|HAS_NO_OWNER]->(peer)
    RETURN r.branch AS branch, r.status AS status, peer.uuid AS peer_id, r.from AS from_time, r.to AS to_time
    ORDER BY from_time, peer_id, status
    """
    results = await db.execute_query(query=query, params={"node_id": node_id})
    return [(row["branch"], row["status"], row["peer_id"], row["from_time"], row["to_time"]) for row in results]


async def update_diff(
    db: InfrahubDatabase, default_branch: Branch, branch: Branch, diff_repository: DiffRepository
) -> EnrichedDiffRoot:
    coordinator = await get_diff_coordinator(db=db, branch=branch)
    metadata = await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    return await diff_repository.get_one(diff_branch_name=branch.name, diff_id=metadata.uuid)


async def merge(db: InfrahubDatabase, branch: Branch) -> None:
    """Merge the branch with its latest diff, the way the merge of a branch does after the diff update."""
    merger = await get_diff_merger(db=db, branch=branch)
    await merger.merge_graph(at=Timestamp())


def owner_property(diff: EnrichedDiffRoot, node_id: str, field_name: str = OWNERS_FIELD) -> EnrichedDiffProperty:
    node = get_one_diff_node(diff_root=diff, node_uuid=node_id)
    return node.get_attribute(name=field_name).get_property(property_type=DatabaseEdgeType.HAS_OWNER)


def has_owner_change(diff: EnrichedDiffRoot) -> bool:
    return any(attribute.name == OWNERS_FIELD for node in diff.nodes for attribute in node.attributes)
