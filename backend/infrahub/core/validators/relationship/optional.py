from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Sequence

# from infrahub.core.branch import Branch
from infrahub.core.constants import PathResourceType, PathType
from infrahub.core.path import DataPath

# from infrahub.database import InfrahubDatabase
from ..shared import RelationshipSchemaValidator, SchemaValidatorQuery, SchemaViolation

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class RelationshipOptionalUpdateValidatorQuery(SchemaValidatorQuery):
    name = "relationship_constraints_optional_validator"

    def __init__(
        self,
        *args: Any,
        validator: RelationshipOptionalUpdateValidator,
        **kwargs: Any,
    ):
        self.validator = validator

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Dict[str, Any]) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["node_kind"] = self.validator.node_schema.kind
        self.params["relationship_id"] = self.validator.relationship_schema.identifier

        query = """
        // Query all Active Nodes of type
        // and store their UUID in uuids_with_rel
        MATCH (n:Node)
        WHERE $node_kind IN LABELS(n)
        CALL {
            WITH n
            MATCH (root:Root)<-[r:IS_PART_OF]-(n)
            WHERE %(branch_filter)s
            RETURN n as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as active_node, r1 as rb, n
        WHERE rb.status = "active"
        WITH COLLECT(active_node.uuid) AS uuids_active_node
        // identifier all nodes with at least one active member for this relationship
        // and store their UUID in uuids_with_rel
        MATCH (n:Node)
        WHERE $node_kind IN LABELS(n)
        CALL {
            WITH n, uuids_active_node
            MATCH path = (n)-[r:IS_RELATED]-(:Relationship { name: $relationship_id })
            WHERE %(branch_filter)s
            RETURN n as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as node_with_rel, r1 as r, uuids_active_node
        WHERE r.status = "active"
        WITH COLLECT(node_with_rel.uuid) AS uuids_with_rel, uuids_active_node
        MATCH (n:Node)
        WHERE $node_kind IN LABELS(n)
          AND n.uuid IN uuids_active_node
          AND not n.uuid IN uuids_with_rel
          AND NOT exists((n)-[:IS_RELATED]-(:Relationship { name: $relationship_id }))
        """ % {"branch_filter": branch_filter}

        self.add_to_query(query)
        self.return_labels = ["n.uuid"]

    async def get_paths(self) -> List[DataPath]:
        paths = []
        for result in self.results:
            paths.append(
                DataPath(  # type: ignore[call-arg]
                    resource_type=PathResourceType.DATA,
                    path_type=PathType.NODE,
                    node_id=str(result.get("n.uuid")),
                    kind=self.validator.node_schema.kind,
                )
            )

        return paths


class RelationshipOptionalUpdateValidator(RelationshipSchemaValidator):
    name: str = "relationship.optional.update"
    queries: Sequence[type[SchemaValidatorQuery]] = [RelationshipOptionalUpdateValidatorQuery]

    async def run_validate(self, db: InfrahubDatabase, branch: Branch) -> List[SchemaViolation]:
        # if the new schema has the relationship as Optional == True
        # there is no need to validate the data at all
        if self.relationship_schema.optional is True:
            return []
        return await super().run_validate(db=db, branch=branch)
