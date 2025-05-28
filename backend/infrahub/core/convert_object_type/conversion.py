from typing import Any

from pydantic import BaseModel

from infrahub.core.attribute import BaseAttribute
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.query.relationship import GetAllPeersIds
from infrahub.core.relationship import RelationshipManager
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase


class InputDataForDestField(BaseModel):  # Only one of these fields can be not None
    attribute_value: Any | None = None
    peer_id: str | None = None
    peers_ids: list[str] | None = None

    @property
    def value(self) -> Any:
        fields = [self.attribute_value, self.peer_id, self.peers_ids]
        set_fields = [f for f in fields if f is not None]
        if len(set_fields) != 1:
            raise ValueError("Exactly one of attribute_value, peer_id, or peers_ids must be set")
        return set_fields[0]


class InputForDestField(BaseModel):  # Only one of these fields can be not None
    source_field: str | None = None
    data: InputDataForDestField | None = None

    @property
    def value(self) -> Any:
        if self.source_field is not None and self.data is not None:
            raise ValueError("Only one of source_field or data can be set")
        if self.source_field is None and self.data is None:
            raise ValueError("Either source_field or data must be set")
        return self.source_field if self.source_field is not None else self.data


async def get_out_rels_peers_ids(node: Node, db: InfrahubDatabase) -> list[str]:
    all_peers: list[Node] = []
    for name in node._relationships:
        relm: RelationshipManager = getattr(node, name)
        peers = await relm.get_peers(db=db)
        all_peers.extend(peers.values())
    return [peer.id for peer in all_peers]


async def build_data_new_node(db: InfrahubDatabase, mapping: dict[str, InputForDestField], node: Node) -> dict:
    """Value of a given field on the target kind to convert is either an input source attribute/relationship of the source node,
    or a raw value."""

    data = {}
    for dest_field_name, input_for_dest_field in mapping.items():
        value = input_for_dest_field.value
        if isinstance(value, str):  # source_field
            item = getattr(node, value)
            if isinstance(item, BaseAttribute):
                data[dest_field_name] = item.value
            elif isinstance(item, RelationshipManager):
                if item.schema.cardinality == RelationshipCardinality.ONE:
                    peer = await item.get_peer(db=db)
                    if peer is not None:
                        data[dest_field_name] = {"id": peer.id}
                    # else, relationship is optional, and if the target relationship is mandatory an error will be raised during creation
                elif item.schema.cardinality == RelationshipCardinality.MANY:
                    data[dest_field_name] = [{"id": peer.id} for _, peer in (await item.get_peers(db=db)).items()]
                else:
                    raise ValueError(f"Unknown cardinality {item.schema.cardinality=}")
        else:  # user input data
            data[dest_field_name] = value.value
    return data


async def get_unidirectional_rels_peers_ids(node: Node, branch: Branch, db: InfrahubDatabase) -> list[str]:
    """
    Returns peers ids of nodes connected to input `node` through an incoming unidirectional relationship.
    """

    out_rels_identifier = [rel.identifier for rel in node.get_schema().relationships]
    query = await GetAllPeersIds.init(db=db, node_id=node.id, branch=branch, exclude_identifiers=out_rels_identifier)
    await query.execute(db=db)
    return query.get_peers_uuids()


async def convert_object_type(
    node: Node, target_schema: NodeSchema, mapping: dict[str, InputForDestField], branch: Branch, db: InfrahubDatabase
) -> Node:
    """Delete the node and return the new created one. If creation fails, the node is not deleted, and raise an error.
    An extra check is performed on input node peers relationships to make sure they are still valid."""

    node_schema = node.get_schema()
    if not isinstance(node_schema, NodeSchema):
        raise ValueError(f"Only a node with a NodeSchema can be converted, got {type(node_schema)}")

    async with db.start_transaction() as dbt:
        deleted_node_out_rels_peer_ids = await get_out_rels_peers_ids(node=node, db=dbt)
        deleted_node_unidir_rels_peer_ids = await get_unidirectional_rels_peers_ids(node=node, db=dbt, branch=branch)

        deleted_nodes = await NodeManager.delete(db=dbt, branch=branch, nodes=[node], cascade_delete=False)
        if len(deleted_nodes) != 1:
            raise ValueError(f"Deleted {len(deleted_nodes)} nodes instead of 1")

        data_new_node = await build_data_new_node(dbt, mapping, node)
        node_created = await create_node(
            data=data_new_node,
            db=dbt,
            branch=branch,
            schema=target_schema,
        )

        # Make sure relationships with constraints are not broken by retrieving them
        peers_ids = deleted_node_out_rels_peer_ids + deleted_node_unidir_rels_peer_ids
        peers = await NodeManager.get_many(ids=peers_ids, db=dbt, prefetch_relationships=True, branch=branch)
        for peer in peers.values():
            peer.validate_relationships()

        return node_created
