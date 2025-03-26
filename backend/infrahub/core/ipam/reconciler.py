import ipaddress
from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.ipam import IPPrefixReconcileQuery
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase, retry_db_transaction
from infrahub.exceptions import NodeNotFoundError

from .constants import AllIPTypes

if TYPE_CHECKING:
    from infrahub.core.relationship.model import RelationshipManager


class IPNodesToReconcile:
    def __init__(
        self,
        node_uuid: str,
        current_parent_uuid: str | None,
        calculated_parent_uuid: str | None,
        current_child_uuids: set[str],
        calculated_child_uuids: set[str],
        node_map: dict[str, Node],
    ) -> None:
        self.node_uuid = node_uuid
        self.current_parent_uuid = current_parent_uuid
        self.calculated_parent_uuid = calculated_parent_uuid
        self.current_child_uuids = current_child_uuids
        self.calculated_child_uuids = calculated_child_uuids
        self.node_map = node_map
        self._calculated_child_nodes = set()
        self._current_child_nodes = set()
        for ccu in self.current_child_uuids:
            if ccu in self.node_map:
                self._current_child_nodes.add(self.node_map[ccu])
        for ccu in self.calculated_child_uuids:
            if ccu in self.node_map:
                self._calculated_child_nodes.add(self.node_map[ccu])

    @property
    def node(self) -> Node:
        return self.node_map[self.node_uuid]

    @property
    def current_parent(self) -> Node | None:
        if not self.current_parent_uuid:
            return None
        return self.node_map.get(self.current_parent_uuid)

    @property
    def calculated_parent(self) -> Node | None:
        if not self.calculated_parent_uuid:
            return None
        return self.node_map.get(self.calculated_parent_uuid)

    @property
    def current_child_nodes(self) -> set[Node]:
        return self._current_child_nodes

    @property
    def calculated_child_nodes(self) -> set[Node]:
        return self._calculated_child_nodes

    def get_node_by_uuid(self, uuid: str) -> Node:
        return self.node_map[uuid]

    async def _get_child_uuids(self, db: InfrahubDatabase, node: Node | None) -> set[str]:
        if not node:
            return set()
        child_uuids = set()
        child_prefix_rels = await node.children.get_relationships(db=db, force_refresh=False)  # type: ignore[attr-defined]
        child_uuids |= {cpr.get_peer_id() for cpr in child_prefix_rels}
        child_address_rels = await node.ip_addresses.get_relationships(db=db, force_refresh=False)  # type: ignore[attr-defined]
        child_uuids |= {car.get_peer_id() for car in child_address_rels}
        return child_uuids


class IpamReconciler:
    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch
        self.at: Timestamp | None = None

    @retry_db_transaction(name="ipam_reconcile")
    async def reconcile(
        self,
        ip_value: AllIPTypes,
        namespace: Node | str | None = None,
        node_uuid: str | None = None,
        is_delete: bool = False,
        at: Timestamp | None = None,
    ) -> Node | None:
        self.at = Timestamp(at)

        query = await IPPrefixReconcileQuery.init(
            db=self.db, branch=self.branch, ip_value=ip_value, namespace=namespace, node_uuid=node_uuid, at=self.at
        )
        await query.execute(db=self.db)

        ip_node_uuid = query.get_ip_node_uuid()
        if not ip_node_uuid:
            node_type = InfrahubKind.IPPREFIX
            if isinstance(ip_value, ipaddress.IPv6Interface | ipaddress.IPv4Interface):
                node_type = InfrahubKind.IPADDRESS
            raise NodeNotFoundError(node_type=node_type, identifier=str(ip_value))
        current_parent_uuid = query.get_current_parent_uuid()
        calculated_parent_uuid = query.get_calculated_parent_uuid()
        current_children_uuids = set(query.get_current_children_uuids())
        calculated_children_uuids = set(query.get_calculated_children_uuids())

        all_uuids: set[str] = set()
        all_uuids = (all_uuids | {ip_node_uuid}) if ip_node_uuid else all_uuids
        all_uuids = (all_uuids | {current_parent_uuid}) if current_parent_uuid else all_uuids
        all_uuids = (all_uuids | {calculated_parent_uuid}) if calculated_parent_uuid else all_uuids
        all_uuids |= current_children_uuids
        all_uuids |= calculated_children_uuids
        all_nodes = await NodeManager.get_many(
            db=self.db,
            branch=self.branch,
            ids=list(all_uuids),
        )

        reconcile_nodes = IPNodesToReconcile(
            node_uuid=ip_node_uuid,
            current_parent_uuid=current_parent_uuid,
            calculated_parent_uuid=calculated_parent_uuid,
            current_child_uuids=current_children_uuids,
            calculated_child_uuids=calculated_children_uuids,
            node_map=all_nodes,
        )

        if is_delete:
            updated_uuids = await self.update_children_for_delete(reconcile_nodes)
        else:
            updated_uuids = await self.update_node(reconcile_nodes)
            updated_uuids |= await self.update_current_children(reconcile_nodes)
            updated_uuids |= await self.update_calculated_children(reconcile_nodes)

        for updated_uuid in updated_uuids:
            node = reconcile_nodes.get_node_by_uuid(updated_uuid)
            await node.save(db=self.db, at=self.at)

        if is_delete:
            try:
                await reconcile_nodes.node.delete(db=self.db, at=self.at)
            except KeyError:
                return None

        return reconcile_nodes.node

    async def _update_node_parent(self, node: Node, new_parent_uuid: str | None) -> None:
        node_kinds = {node.get_kind()} | set(node.get_schema().inherit_from)
        is_prefix = False
        if InfrahubKind.IPADDRESS in node_kinds:
            rel_manager: RelationshipManager = node.ip_prefix  # type: ignore[attr-defined]
        elif InfrahubKind.IPPREFIX in node_kinds:
            rel_manager = node.parent  # type: ignore[attr-defined]
            is_prefix = True
        else:
            return

        await rel_manager.update(db=self.db, data=new_parent_uuid)
        if not is_prefix:
            return
        node.is_top_level.value = new_parent_uuid is None  # type: ignore[attr-defined]

    async def update_node(self, reconcile_nodes: IPNodesToReconcile) -> set[str]:
        await self._update_node_parent(
            node=reconcile_nodes.node, new_parent_uuid=reconcile_nodes.calculated_parent_uuid
        )
        return {reconcile_nodes.node.get_id()}

    async def update_node_for_delete(self, reconcile_nodes: IPNodesToReconcile) -> set[str]:
        await self._update_node_parent(node=reconcile_nodes.node, new_parent_uuid=None)
        return {reconcile_nodes.node.get_id()}

    async def update_current_children(self, reconcile_nodes: IPNodesToReconcile) -> set[str]:
        updated_uuids = set()
        for current_child_node in reconcile_nodes.current_child_nodes:
            current_child_uuid = current_child_node.get_id()
            if current_child_uuid in reconcile_nodes.calculated_child_uuids:
                # current child is still a child, no update necessary
                continue
            # set parent of deleted child to current_parent of the node (might be None)
            await self._update_node_parent(node=current_child_node, new_parent_uuid=reconcile_nodes.current_parent_uuid)
            updated_uuids.add(current_child_uuid)
        return updated_uuids

    async def update_calculated_children(self, reconcile_nodes: IPNodesToReconcile) -> set[str]:
        updated_uuids = set()
        for calculated_child_node in reconcile_nodes.calculated_child_nodes:
            calculated_child_uuid = calculated_child_node.get_id()
            if calculated_child_uuid in reconcile_nodes.current_child_uuids:
                # calculated child is already a child, no update necessary
                continue
            # set parent of new child to the node
            await self._update_node_parent(node=calculated_child_node, new_parent_uuid=reconcile_nodes.node_uuid)
            updated_uuids.add(calculated_child_uuid)
        return updated_uuids

    async def update_children_for_delete(self, reconcile_nodes: IPNodesToReconcile) -> set[str]:
        updated_uuids = set()
        for current_child_node in reconcile_nodes.current_child_nodes:
            current_child_uuid = current_child_node.get_id()
            await self._update_node_parent(node=current_child_node, new_parent_uuid=reconcile_nodes.current_parent_uuid)
            updated_uuids.add(current_child_uuid)
        return updated_uuids
