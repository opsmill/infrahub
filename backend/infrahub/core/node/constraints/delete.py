from typing import List, Optional, Tuple

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.query.node import NodeListGetRelationshipsQuery
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError

from .interface import NodeConstraintInterface


class NodeDeleteConstraint(NodeConstraintInterface):
    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch

    async def check(self, node: Node, at: Optional[Timestamp] = None, filters: Optional[List[str]] = None) -> None:
        query = await NodeListGetRelationshipsQuery.init(db=self.db, ids=[node.id], branch=self.branch, at=at)
        await query.execute(db=self.db)

        relationships_to_check: List[Tuple[str, str, str]] = []
        for result_row in query.results:
            relationship_identifier = result_row.get("rel").get("name")
            peer_id = result_row.get("peer").get("uuid")
            peer_kind = result_row.get("peer").get("kind")
            if relationship_identifier and peer_id and peer_kind:
                relationships_to_check.append((relationship_identifier, peer_id, peer_kind))

        schema_branch = registry.schema.get_schema_branch(name=self.branch.name)
        validation_errors = []
        for rel_id, source_id, source_kind in relationships_to_check:
            source_schema = schema_branch.get(name=source_kind, duplicate=False)
            relationship_schema = source_schema.get_relationship_by_identifier(id=rel_id, raise_on_error=False)
            if not relationship_schema:
                continue
            if relationship_schema.optional is False:
                location = f"{source_schema.kind}.{relationship_schema.name}"
                validation_errors.append(
                    ValidationError(
                        {location: f"Cannot delete. Node is linked to mandatory relationship on node {source_id}"}
                    )
                )

        if validation_errors:
            raise ValidationError(validation_errors)
