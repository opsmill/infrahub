from typing import Any, assert_never

from infrahub_sdk.convert_object_type import ConversionFieldInput, ConversionFieldValue

from infrahub.core.attribute import BaseAttribute
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import BranchSupportType, RelationshipCardinality
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.query.relationship import GetAllPeersIds
from infrahub.core.query.resource_manager import PoolChangeReserved
from infrahub.core.relationship import RelationshipManager
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.message_bus.messages import RefreshRegistryBranches
from infrahub.tasks.registry import update_branch_registry
from infrahub.workers.dependencies import get_message_bus


def _get_conversion_field_raw_value(conv_field_value: ConversionFieldValue) -> Any:
    if conv_field_value.attribute_value is not None:
        return conv_field_value.attribute_value
    if conv_field_value.peer_id is not None:
        return conv_field_value.peer_id
    if conv_field_value.peers_ids is not None:
        return conv_field_value.peers_ids
    raise ValueError("ConversionFieldValue has not been validated correctly.")


async def get_out_rels_peers_ids(node: Node, db: InfrahubDatabase, at: Timestamp) -> list[str]:
    all_peers_ids: list[str] = []
    for name in node._relationships:
        relm: RelationshipManager = getattr(node, name)
        peers = await relm.get_db_peers(db=db, at=at)
        all_peers_ids.extend([str(peer.peer_id) for peer in peers])
    return all_peers_ids


async def build_data_new_node(db: InfrahubDatabase, mapping: dict[str, ConversionFieldInput], node: Node) -> dict:
    """Value of a given field on the target kind to convert is either an input source attribute/relationship of the source node,
    or a raw value."""

    data = {}
    for dest_field_name, conv_field_input in mapping.items():
        if conv_field_input.source_field is not None:
            # Fetch the value of the corresponding field from the node being converted.
            item = getattr(node, conv_field_input.source_field)
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
                    assert_never(item.schema.cardinality)
        elif conv_field_input.data is not None:
            data[dest_field_name] = _get_conversion_field_raw_value(conv_field_input.data)
        elif conv_field_input.use_default_value is True:
            pass  # default value will be used automatically when creating the node
        else:
            raise ValueError("ConversionFieldInput has not been validated correctly.")
    return data


async def get_unidirectional_rels_peers_ids(
    node: Node, branch: Branch, db: InfrahubDatabase, at: Timestamp
) -> list[str]:
    """
    Returns peers ids of nodes connected to input `node` through an incoming unidirectional relationship.
    """

    out_rels_identifier = [rel.identifier for rel in node.get_schema().relationships]
    branch_agnostic = node.get_schema().branch == BranchSupportType.AGNOSTIC
    query = await GetAllPeersIds.init(
        db=db,
        node_id=node.id,
        branch=branch,
        exclude_identifiers=out_rels_identifier,
        branch_agnostic=branch_agnostic,
        at=at,
    )
    await query.execute(db=db)
    return query.get_peers_uuids()


async def _get_other_active_branches(db: InfrahubDatabase) -> list[Branch]:
    branches = await Branch.get_list(db=db)
    return [branch for branch in branches if not (branch.is_global or branch.is_default)]


def _has_pass_thru_aware_attributes(node_schema: NodeSchema, mapping: dict[str, ConversionFieldInput]) -> bool:
    aware_attributes = [attr for attr in node_schema.attributes if attr.branch != BranchSupportType.AGNOSTIC]
    aware_attributes_pass_thru = [
        attr.name for attr in aware_attributes if attr.name in mapping and mapping[attr.name].source_field is not None
    ]
    return len(aware_attributes_pass_thru) > 0


async def validate_conversion(
    deleted_node: Node, branch: Branch, db: InfrahubDatabase, timestamp_before_conversion: Timestamp
) -> None:
    deleted_node_out_rels_peer_ids = await get_out_rels_peers_ids(
        node=deleted_node, db=db, at=timestamp_before_conversion
    )
    deleted_node_unidir_rels_peer_ids = await get_unidirectional_rels_peers_ids(
        node=deleted_node, db=db, branch=branch, at=timestamp_before_conversion
    )

    # Make sure relationships with constraints are not broken by retrieving them
    peers_ids = deleted_node_out_rels_peer_ids + deleted_node_unidir_rels_peer_ids
    peers = await NodeManager.get_many(ids=peers_ids, db=db, prefetch_relationships=True, branch=branch)
    for peer in peers.values():
        peer.validate_relationships()


async def convert_and_validate_object_type(
    node: Node,
    target_schema: NodeSchema,
    mapping: dict[str, ConversionFieldInput],
    branch: Branch,
    db: InfrahubDatabase,
) -> Node:
    async with db.start_transaction() as dbt:
        timestamp_before_conversion = Timestamp()
        new_node = await convert_object_type(
            node=node, target_schema=target_schema, mapping=mapping, branch=branch, db=dbt
        )
        await validate_conversion(
            deleted_node=node, branch=branch, db=dbt, timestamp_before_conversion=timestamp_before_conversion
        )

    # Refresh outside the transaction otherwise other workers would pull outdated branch objects.
    message_bus = await get_message_bus()
    await message_bus.send(RefreshRegistryBranches())

    return new_node


async def convert_object_type(
    node: Node,
    target_schema: NodeSchema,
    mapping: dict[str, ConversionFieldInput],
    branch: Branch,
    db: InfrahubDatabase,
) -> Node:
    """Delete the node and return the new created one. If creation fails, the node is not deleted, and raise an error.
    An extra check is performed on input node peers relationships to make sure they are still valid."""

    node_schema = node.get_schema()
    if not isinstance(node_schema, NodeSchema):
        raise ValueError(f"Only a node with a NodeSchema can be converted, got {type(node_schema)}")

    # Delete the node, so we delete relationships with peers as well, which might temporarily break cardinality constraints
    # but they should be restored when creating the new node.
    deleted_nodes = await NodeManager.delete(db=db, branch=branch, nodes=[node], cascade_delete=False)
    if len(deleted_nodes) != 1:
        raise ValueError(f"Deleted {len(deleted_nodes)} nodes instead of 1")

    data_new_node = await build_data_new_node(db, mapping, node)

    if node_schema.branch == BranchSupportType.AGNOSTIC and _has_pass_thru_aware_attributes(
        node_schema=node_schema, mapping=mapping
    ):
        if not branch.is_default:
            raise ValueError(
                f"Conversion of {node_schema.kind} is not allowed on branch {branch.name} because it is agnostic and has aware attributes"
            )

        # When converting an agnostic node with aware attributes, we need to put other branches in NEED_REBASE state
        # as aware attributes do not exist in other branches after conversion
        other_branches = await _get_other_active_branches(db=db)
        for br in other_branches:
            br.status = BranchStatus.NEED_REBASE
            await br.save(db=db)
            # Registry of other API workers are updated outside the transaction
            await update_branch_registry(db=db, branch=br)

    node_created = await create_node(
        data=data_new_node,
        db=db,
        branch=branch,
        schema=target_schema,
    )

    # If the node had some value reserved in any Pools / Resource Manager, we need to change the identifier of the reservation(s)
    query = await PoolChangeReserved.init(
        db=db,
        existing_identifier=node.get_id(),
        new_identifier=node_created.get_id(),
        branch=branch,
    )
    await query.execute(db=db)

    return node_created
