from typing import Any

from pydantic import BaseModel

from infrahub.core import registry
from infrahub.core.attribute import BaseAttribute
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.convert_object_type.schema_mapping import raise_if_unidirectional_relationships
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node, validate_node_relationships
from infrahub.core.relationship import RelationshipManager
from infrahub.core.schema import NodeSchema
from infrahub.database import InfrahubDatabase
from infrahub.graphql.mutations.mutation_create import create_node


class InputDataForDestField(BaseModel):  # Only one of these fields can be not None
    attribute_value: Any | None = None
    peer_id: str | None = None
    peers_ids: list[str] | None = None


class InputForDestField(BaseModel):  # Only one of these fields can be not None
    source_field: str | None = None
    data: InputDataForDestField | None = None


async def get_all_peers_ids(node: Node, db: InfrahubDatabase) -> list[str]:
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
        if input_for_dest_field.source_field is not None:
            item = getattr(node, input_for_dest_field.source_field)
            if isinstance(item, BaseAttribute):
                data[dest_field_name] = item.value
            elif isinstance(item, RelationshipManager):
                if item.schema.cardinality == RelationshipCardinality.ONE:
                    peer = await item.get_peer(db=db)
                    if peer is None:
                        raise ValueError(f"Unable to find peer of {item=}")
                    data[dest_field_name] = {"id": peer.id}
                elif item.schema.cardinality == RelationshipCardinality.MANY:
                    data[dest_field_name] = [{"id": peer.id} for _, peer in (await item.get_peers(db=db)).items()]
                else:
                    raise ValueError(f"Unknown cardinality {item.schema.cardinality=}")
        else:
            assert input_for_dest_field.data is not None, f"{input_for_dest_field=}"
            if input_for_dest_field.data.attribute_value is not None:
                data[dest_field_name] = input_for_dest_field.data.attribute_value
            elif input_for_dest_field.data.peer_id is not None:
                data[dest_field_name] = input_for_dest_field.data.peer_id
            elif input_for_dest_field.data.peers_ids is not None:
                data[dest_field_name] = input_for_dest_field.data.peers_ids
            else:
                raise ValueError(f"No filled value for destination field {dest_field_name=}")
    return data


async def convert_object_type(
    node: Node, target_kind: str, mapping: dict[str, InputForDestField], branch: Branch, db: InfrahubDatabase
) -> Node:
    """Delete the node and return the new created one. If creation fails, the node is not deleted, and raise an error."""

    node_schema = node.get_schema()
    if not isinstance(node_schema, NodeSchema):
        raise ValueError(f"Only a node with a NodeSchema can be converted, got {type(node_schema)}")

    raise_if_unidirectional_relationships(node_schema)

    async with db.start_transaction() as dbt:  # noqa: PLR1702
        data_new_node = await build_data_new_node(dbt, mapping, node)
        deleted_node_peer_ids = await get_all_peers_ids(node=node, db=dbt)
        deleted_nodes = await NodeManager.delete(db=dbt, branch=branch, nodes=[node], cascade_delete=False)
        if len(deleted_nodes) != 1:
            raise ValueError(f"Deleted {len(deleted_nodes)} nodes instead of 1")

        target_schema = registry.get_node_schema(name=target_kind, branch=branch)
        node_created = await create_node(
            data=data_new_node,
            db=dbt,
            branch=branch,
            schema=target_schema,
            use_session_for_constraint_checks=False,
        )

        # Make sure relationships with constraints are not broken by retrieving them
        for peer_id in deleted_node_peer_ids:
            peer = await NodeManager.get_one(id=peer_id, db=dbt, prefetch_relationships=True, branch=branch)
            if peer is None:
                raise ValueError(f"Peer {peer_id} not found after deleting node {node.id}")

            validate_node_relationships(node=peer)

        return node_created
