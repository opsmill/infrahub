from dataclasses import dataclass
from typing import Iterable, Optional, Union

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipDeleteBehavior
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.node import NodeListGetRelationshipsQuery
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


@dataclass
class DependantNodeDetails:
    node_id: str
    node_schema: Union[NodeSchema, GenericSchema]
    dependant_node_id: str
    dependant_node_schema: Union[NodeSchema, GenericSchema]
    dependant_node_relationship_schema: RelationshipSchema


class NodeDeleter:
    def __init__(self, db: InfrahubDatabase, branch: Branch):
        self.db = db
        self.branch = branch
        self._dependant_node_details: list[DependantNodeDetails] = []
        self._node_ids_to_delete: set[str] = set()

    async def delete(self, nodes: Iterable[Node], at: Optional[Union[Timestamp, str]] = None) -> None:
        at = Timestamp(at)
        self._dependant_node_details = []
        self._node_ids_to_delete = set()

        await self._analyze_nodes_to_delete(start_node_ids=[n.id for n in nodes], at=at)

        validation_errors = []
        for dnd in self._dependant_node_details:
            if dnd.dependant_node_id not in self._node_ids_to_delete:
                peer_kind = dnd.dependant_node_schema.kind
                peer_rel_name = dnd.dependant_node_relationship_schema.name
                peer_path = f"{peer_kind}.{peer_rel_name}"
                err_msg = f"Cannot delete {dnd.node_schema.kind} '{dnd.node_id}'."
                err_msg += f" It is linked to mandatory relationship {peer_rel_name} on node {peer_kind} '{dnd.dependant_node_id}'"
                validation_errors.append(ValidationError({peer_path: err_msg}))

        if validation_errors:
            raise ValidationError(validation_errors)

        nodes_by_id = await NodeManager.get_many(
            db=self.db, ids=list(self._node_ids_to_delete), at=at, branch=self.branch
        )
        async with self.db.start_transaction() as db:
            for node in nodes_by_id.values():
                await node.delete(db=db, at=at)

    async def _analyze_nodes_to_delete(
        self, start_node_ids: Iterable[str], at: Optional[Union[Timestamp, str]]
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=self.branch.name)
        node_ids_to_delete = set(start_node_ids)
        _next_node_ids_to_delete = set()

        query = await NodeListGetRelationshipsQuery.init(
            db=self.db, ids=list(start_node_ids), branch=self.branch, at=at
        )
        await query.execute(db=self.db)

        for result_row in query.results:
            node_id = result_row.get("n").get("uuid")
            node_kind = result_row.get("n").get("kind")
            relationship_identifier = result_row.get("rel").get("name")
            peer_id = result_row.get("peer").get("uuid")
            peer_kind = result_row.get("peer").get("kind")
            if not all((node_id, node_kind, relationship_identifier, peer_id, peer_kind)):
                continue

            node_schema = schema_branch.get(name=node_kind, duplicate=False)
            peer_schema = schema_branch.get(name=peer_kind, duplicate=False)
            node_relationship_schema = node_schema.get_relationship_by_identifier(
                id=relationship_identifier, raise_on_error=False
            )
            peer_relationship_schema = peer_schema.get_relationship_by_identifier(
                id=relationship_identifier, raise_on_error=False
            )

            if (
                peer_id not in node_ids_to_delete
                and node_relationship_schema
                and node_relationship_schema.delete_behavior == RelationshipDeleteBehavior.CASCADE
            ):
                _next_node_ids_to_delete.add(peer_id)

            if peer_relationship_schema and peer_relationship_schema.optional is False:
                self._dependant_node_details.append(
                    DependantNodeDetails(
                        node_id=node_id,
                        node_schema=node_schema,
                        dependant_node_id=peer_id,
                        dependant_node_schema=peer_schema,
                        dependant_node_relationship_schema=peer_relationship_schema,
                    )
                )

        self._node_ids_to_delete |= node_ids_to_delete
        if not _next_node_ids_to_delete:
            return

        unchecked_node_ids = _next_node_ids_to_delete - self._node_ids_to_delete
        if not unchecked_node_ids:
            return

        await self._analyze_nodes_to_delete(start_node_ids=unchecked_node_ids, at=at)
