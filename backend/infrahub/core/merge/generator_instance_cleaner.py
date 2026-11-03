from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import DiffAction, InfrahubKind, RelationshipDirection
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.manager import NodeManager
from infrahub.core.query.node import NodeListGetRelationshipsQuery
from infrahub.core.registry import registry
from infrahub.log import get_logger

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.log import InfrahubLogger


class GeneratorInstanceCleaner:
    """Delete the generator instances on the destination branch whose target or definition a merge deleted.

    Generator instances are branch-local, so a deletion made on the source branch never reaches them.
    """

    batch_size = 500

    def __init__(
        self,
        db: InfrahubDatabase,
        source_branch: Branch,
        destination_branch: Branch,
        diff_repository: DiffRepository,
        logger: InfrahubLogger | None = None,
    ) -> None:
        self.db = db
        self.source_branch = source_branch
        self.destination_branch = destination_branch
        self.diff_repository = diff_repository
        self.log = logger or get_logger()

    async def find_orphaned_instances(self, merge_at: Timestamp) -> set[str]:
        """Return the generator instances that require a node the merge deleted on the destination branch."""
        deleted_node_uuids = await self.diff_repository.get_affected_node_uuids(
            diff_branch_name=self.source_branch.name,
            tracking_id=BranchTrackingId(name=self.source_branch.name),
            include_actions=[DiffAction.REMOVED],
        )
        if not deleted_node_uuids:
            return set()
        # The merge closed the edges that link an instance to a deleted node, so read them as they were before it.
        instance_ids_by_node = await self._get_instances_by_node(
            node_uuids=deleted_node_uuids, at=merge_at.subtract(microseconds=1)
        )
        # A deletion that a conflict resolved to the base branch is in the diff but did not reach the destination.
        remaining_nodes = await NodeManager.get_many(
            db=self.db, ids=list(instance_ids_by_node), branch=self.destination_branch, at=merge_at
        )
        return {
            instance_id
            for node_uuid, instance_ids in instance_ids_by_node.items()
            if node_uuid not in remaining_nodes
            for instance_id in instance_ids
        }

    async def delete(self, instance_ids: set[str], user_id: str) -> None:
        if not instance_ids:
            return
        instances = await NodeManager.get_many(db=self.db, ids=list(instance_ids), branch=self.destination_branch)
        self.log.info(f"Deleting {len(instances)} generator instances whose target or definition the merge deleted")
        await NodeManager.delete(
            db=self.db, nodes=list(instances.values()), branch=self.destination_branch, user_id=user_id
        )

    async def _get_instances_by_node(self, node_uuids: list[str], at: Timestamp) -> dict[str, set[str]]:
        instance_schema = registry.schema.get(
            name=InfrahubKind.GENERATORINSTANCE, branch=self.destination_branch, duplicate=False
        )
        identifiers = [rel.get_identifier() for rel in instance_schema.relationships if not rel.optional]
        instance_ids_by_node: dict[str, set[str]] = {}
        for i in range(0, len(node_uuids), self.batch_size):
            batch_uuids = node_uuids[i : i + self.batch_size]
            query = await NodeListGetRelationshipsQuery.init(
                db=self.db,
                branch=self.destination_branch,
                at=at,
                ids=batch_uuids,
                outbound_identifiers=[],
                inbound_identifiers=[],
                bidirectional_identifiers=identifiers,
            )
            await query.execute(db=self.db)
            peers = query.get_peers_group_by_node()
            for node_uuid in batch_uuids:
                instance_ids = {
                    peer_id
                    for identifier in identifiers
                    for peer_id in peers.get_peer_ids(
                        node_id=node_uuid, rel_name=identifier, direction=RelationshipDirection.BIDIR
                    )
                    if peers.get_peer_kind(peer_id) == InfrahubKind.GENERATORINSTANCE
                }
                if instance_ids:
                    instance_ids_by_node[node_uuid] = instance_ids
        return instance_ids_by_node
