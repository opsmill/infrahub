from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import lock
from infrahub.core.manager import NodeManager
from infrahub.exceptions import NodeNotFoundError
from infrahub.lock import InfrahubMultiLock
from infrahub.rack_elevation.constants import RackConstraint, RackPlaceArgument
from infrahub.rack_elevation.errors import raise_placement_violation
from infrahub.rack_elevation.locks import rack_lock_name
from infrahub.rack_elevation.models import RackFace, RackItemSnapshot, RackPlacementViolation, RackSnapshot
from infrahub.rack_elevation.placement import check_placement

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.rack_elevation.mapped.mapping import MountableKindFields, RackMappingIndex
    from infrahub.rack_elevation.models import RackElevationKindEntry

NODE_KIND_UNKNOWN = "Node"


class MappedRackElevationProvider:
    """Reads and writes racks through the `rack_elevation` mappings declared in the customer's schema."""

    def __init__(self, db: InfrahubDatabase, branch: Branch, at: Timestamp | None, index: RackMappingIndex) -> None:
        self.db = db
        self.branch = branch
        self.at = at
        self.index = index

    def list_kinds(self) -> list[RackElevationKindEntry]:
        return self.index.list_kinds()

    async def load_rack(self, rack_id: str) -> tuple[RackSnapshot, list[RackItemSnapshot]]:
        rack = await self._rack_snapshot(rack_id=rack_id)
        return rack, await self._load_items(rack_id=rack_id)

    async def load_item(self, item_id: str) -> RackItemSnapshot:
        node = await self._get_node(node_id=item_id, prefetch_relationships=True)
        if node.get_kind() not in self.index.mountable_kinds:
            raise_placement_violation(
                violation=RackPlacementViolation(
                    constraint=RackConstraint.NOT_MOUNTABLE.value,
                    field=RackPlaceArgument.ITEM.value,
                    detail=f"{await node.get_display_label(db=self.db)} cannot be mounted in a rack",
                ),
                node_kind=node.get_kind(),
                field_name=RackPlaceArgument.ITEM.value,
            )
        return (await self._item_snapshots(nodes=[node]))[0]

    async def place(self, item_id: str, rack_id: str, position: int | None, face: RackFace | None) -> RackItemSnapshot:
        item = await self.load_item(item_id=item_id)
        current_rack_id = await self._current_rack_id(item_id=item_id)
        lock_names = sorted({rack_lock_name(self.branch.name, rack) for rack in (rack_id, current_rack_id) if rack})

        async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
            async with self.db.start_transaction() as dbt:
                # Writes happen at the current time, so every read that follows has to be at the current time too.
                writer = MappedRackElevationProvider(db=dbt, branch=self.branch, at=None, index=self.index)
                rack = await writer._rack_snapshot(rack_id=rack_id)
                await writer._write_placement(item_id=item_id, rack_id=rack_id, position=position, face=face)
                items = await writer._load_items(rack_id=rack_id)
                placed = next(candidate for candidate in items if candidate.id == item_id)
                violation = check_placement(
                    rack=rack, others=[other for other in items if other.id != item_id], candidate=placed
                )
                if violation is not None:
                    raise_placement_violation(violation=violation, node_kind=item.kind, field_name=violation.field)
        return placed

    async def find_violation(self, item_id: str) -> RackPlacementViolation | None:
        """Check an item saved with its own mapped attributes against the rack it now sits in.

        An item without a rack is not checked.
        """
        node = await self._get_node(node_id=item_id, prefetch_relationships=True)
        rack_id = await self._current_rack_id(item_id=item_id, node=node)
        if rack_id is None:
            return None
        rack_node = await self._get_node(node_id=rack_id)
        if rack_node.get_kind() not in self.index.rack_fields:
            return RackPlacementViolation(
                constraint=RackConstraint.NOT_A_RACK.value,
                field=RackPlaceArgument.RACK.value,
                detail=f"{await rack_node.get_display_label(db=self.db)} is not a rack",
            )
        rack = await self._rack_snapshot(rack_id=rack_id)
        items = await self._load_items(rack_id=rack_id)
        placed = next(candidate for candidate in items if candidate.id == item_id)
        return check_placement(rack=rack, others=[other for other in items if other.id != item_id], candidate=placed)

    def mountable_fields(self, kind: str) -> MountableKindFields:
        return self.index.mountable_kinds[kind]

    async def _get_node(self, node_id: str, prefetch_relationships: bool = False) -> Node:
        nodes = await NodeManager.get_many(
            db=self.db,
            ids=[node_id],
            branch=self.branch,
            at=self.at,
            prefetch_relationships=prefetch_relationships,
        )
        if node_id not in nodes:
            raise NodeNotFoundError(node_type=NODE_KIND_UNKNOWN, identifier=node_id, branch_name=self.branch.name)
        return nodes[node_id]

    async def _current_rack_id(self, item_id: str, node: Node | None = None) -> str | None:
        node = node or await self._get_node(node_id=item_id, prefetch_relationships=True)
        fields = self.index.mountable_kinds[node.get_kind()]
        return await getattr(node, fields.rack_relationship).get_peer_id(db=self.db)

    async def _rack_snapshot(self, rack_id: str) -> RackSnapshot:
        node = await self._get_node(node_id=rack_id)
        fields = self.index.rack_fields.get(node.get_kind())
        display_label = await node.get_display_label(db=self.db)
        if fields is None:
            raise_placement_violation(
                violation=RackPlacementViolation(
                    constraint=RackConstraint.NOT_A_RACK.value,
                    field=RackPlaceArgument.RACK.value,
                    detail=f"{display_label} is not a rack",
                ),
                node_kind=node.get_kind(),
                field_name=RackPlaceArgument.RACK.value,
            )
        return RackSnapshot(
            id=node.get_id(),
            kind=node.get_kind(),
            display_label=display_label,
            u_height=getattr(node, fields.u_height).value or 0,
        )

    async def _load_items(self, rack_id: str) -> list[RackItemSnapshot]:
        nodes: list[Node] = []
        for kind, fields in self.index.mountable_kinds.items():
            nodes.extend(
                await NodeManager.query(
                    db=self.db,
                    schema=kind,
                    filters={f"{fields.rack_relationship}__ids": [rack_id]},
                    branch=self.branch,
                    at=self.at,
                    prefetch_relationships=True,
                )
            )
        return await self._item_snapshots(nodes=nodes)

    async def _item_snapshots(self, nodes: list[Node]) -> list[RackItemSnapshot]:
        type_ids: dict[str, str | None] = {}
        for node in nodes:
            fields = self.index.mountable_kinds[node.get_kind()]
            type_ids[node.get_id()] = await getattr(node, fields.type_relationship).get_peer_id(db=self.db)
        types = await NodeManager.get_many(
            db=self.db,
            ids=sorted({type_id for type_id in type_ids.values() if type_id}),
            branch=self.branch,
            at=self.at,
        )
        return [
            await self._item_snapshot(node=node, type_node=types.get(type_ids[node.get_id()] or "")) for node in nodes
        ]

    async def _item_snapshot(self, node: Node, type_node: Node | None) -> RackItemSnapshot:
        fields = self.index.mountable_kinds[node.get_kind()]
        position = getattr(node, fields.position_attribute).value
        face = getattr(node, fields.face_attribute).value
        u_height = 0
        full_depth = False
        weight = None
        if type_node is not None:
            type_fields = self.index.type_fields(type_node.get_kind())
            u_height = getattr(type_node, type_fields.height_attribute).value or 0
            full_depth = bool(getattr(type_node, type_fields.depth_attribute).value)
            if type_fields.weight_attribute:
                weight = getattr(type_node, type_fields.weight_attribute).value
        return RackItemSnapshot(
            id=node.get_id(),
            kind=node.get_kind(),
            display_label=await node.get_display_label(db=self.db),
            type_id=type_node.get_id() if type_node else None,
            type_display_label=await type_node.get_display_label(db=self.db) if type_node else None,
            position=position,
            face=RackFace(face) if face else None,
            u_height=u_height,
            full_depth=full_depth,
            weight=weight,
        )

    async def _write_placement(self, item_id: str, rack_id: str, position: int | None, face: RackFace | None) -> None:
        node = await self._get_node(node_id=item_id, prefetch_relationships=True)
        fields = self.index.mountable_kinds[node.get_kind()]
        await getattr(node, fields.position_attribute).from_graphql(data={"value": position})
        await getattr(node, fields.face_attribute).from_graphql(data={"value": face.value if face else None})
        await getattr(node, fields.rack_relationship).update(db=self.db, data={"id": rack_id})
        await node.save(db=self.db, fields=[fields.position_attribute, fields.face_attribute, fields.rack_relationship])
