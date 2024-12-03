from typing import Any

from infrahub.core.branch.models import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.query import Query
from infrahub.database import InfrahubDatabase


class ArtifactDiffQuery(Query):
    name = "get_artifact_diff"

    def __init__(
        self,
        target_branch: Branch,
        target_rel_identifier: str,
        definition_rel_identifier: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.target_branch = target_branch
        self.target_rel_identifier = target_rel_identifier
        self.definition_rel_identifier = definition_rel_identifier

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:
        self.params = {
            "source_branch_name": self.branch.name,
            "target_branch_name": self.target_branch.name,
            "target_rel_identifier": self.target_rel_identifier,
            "definition_rel_identifier": self.definition_rel_identifier,
        }
        query = """
// -----------------------
// get the active artifacts on the source branch
// -----------------------
MATCH (source_artifact:%(artifact_kind)s)-[:IS_PART_OF {branch: $source_branch_name}]->(:Root)
CALL {
    WITH source_artifact
    MATCH (source_artifact)-[root_rel:IS_PART_OF {branch: $source_branch_name}]->(:Root)
    RETURN root_rel
    ORDER BY root_rel.from DESC
    LIMIT 1
}
WITH source_artifact, root_rel
WHERE root_rel.status = "active"
CALL {
    WITH source_artifact
    // -----------------------
    // get the artifact's target node
    // -----------------------
    CALL {
        WITH source_artifact
        OPTIONAL MATCH (source_artifact)-[rrel1:IS_RELATED]-(rel_node:Relationship)-[rrel2:IS_RELATED]-(target_node:Node)
        WHERE rel_node.name = $target_rel_identifier
        AND rrel1.branch = $source_branch_name
        AND rrel2.branch = $source_branch_name
        RETURN target_node, (rrel1.status = "active" AND rrel2.status = "active") AS target_is_active
        ORDER BY rrel1.from DESC, rrel2.from DESC
        LIMIT 1
    }
    // -----------------------
    // get the artifact's definition node
    // -----------------------
    CALL {
        WITH source_artifact
        OPTIONAL MATCH (source_artifact)-[rrel1:IS_RELATED]-(rel_node:Relationship)-[rrel2:IS_RELATED]-(definition_node:Node)
        WHERE rel_node.name = $definition_rel_identifier
        AND rrel1.branch = $source_branch_name
        AND rrel2.branch = $source_branch_name
        RETURN definition_node, (rrel1.status = "active" AND rrel2.status = "active") AS definition_is_active
        ORDER BY rrel1.from DESC, rrel2.from DESC
        LIMIT 1
    }
    // -----------------------
    // get the artifact's checksum
    // -----------------------
    CALL {
        WITH source_artifact
        OPTIONAL MATCH (source_artifact)-[attr_rel:HAS_ATTRIBUTE]->(attr:Attribute)-[value_rel:HAS_VALUE]->(attr_val:AttributeValue)
        WHERE attr.name = "checksum"
        AND attr_rel.branch = $source_branch_name
        AND value_rel.branch = $source_branch_name
        RETURN attr_val.value AS checksum, (attr_rel.status = "active" AND value_rel.status = "active") AS checksum_is_active
        ORDER BY value_rel.from DESC, attr_rel.from DESC
        LIMIT 1
    }
    // -----------------------
    // get the artifact's storage_id
    // -----------------------
    CALL {
        WITH source_artifact
        OPTIONAL MATCH (source_artifact)-[attr_rel:HAS_ATTRIBUTE]->(attr:Attribute)-[value_rel:HAS_VALUE]->(attr_val:AttributeValue)
        WHERE attr.name = "storage_id"
        AND attr_rel.branch = $source_branch_name
        AND value_rel.branch = $source_branch_name
        RETURN attr_val.value AS storage_id, (attr_rel.status = "active" AND value_rel.status = "active") AS storage_id_is_active
        ORDER BY value_rel.from DESC, attr_rel.from DESC
        LIMIT 1
    }
    RETURN CASE
        WHEN target_is_active = TRUE THEN target_node
        ELSE NULL
    END AS target_node,
    CASE
        WHEN definition_is_active = TRUE THEN definition_node
        ELSE NULL
    END AS definition_node,
    CASE
        WHEN checksum_is_active = TRUE THEN checksum
        ELSE NULL
    END AS source_checksum,
    CASE
        WHEN storage_id_is_active = TRUE THEN storage_id
        ELSE NULL
    END AS source_storage_id
}
CALL {
    // -----------------------
    // get the corresponding artifact on the target branch, if it exists
    // -----------------------
    WITH target_node, definition_node
    CALL {
        WITH target_node, definition_node
        OPTIONAL MATCH path = (target_node)-[trel1:IS_RELATED]-(trel_node:Relationship)-[trel2:IS_RELATED]-
        (target_artifact:%(artifact_kind)s)-[drel1:IS_RELATED]-(drel_node:Relationship)-[drel2:IS_RELATED]-(definition_node)
        WHERE trel_node.name = $target_rel_identifier
        AND drel_node.name = $definition_rel_identifier
        AND all(
            r IN relationships(path)
            WHERE r.branch = $target_branch_name
        )
        RETURN
            target_artifact,
            (trel1.status = "active" AND trel2.status = "active" AND drel1.status = "active" AND drel1.status = "active") AS artifact_is_active
        ORDER BY trel1.from DESC, trel2.from DESC, drel1.from DESC, drel2.from DESC
        LIMIT 1
    }
    WITH CASE
        WHEN artifact_is_active = TRUE THEN target_artifact
        ELSE NULL
    END as target_artifact
    // -----------------------
    // get the artifact's checksum on target branch
    // -----------------------
    CALL {
        WITH target_artifact
        OPTIONAL MATCH (target_artifact)-[attr_rel:HAS_ATTRIBUTE]->(attr:Attribute)-[value_rel:HAS_VALUE]->(attr_val:AttributeValue)
        WHERE attr.name = "checksum"
        AND attr_rel.branch = $target_branch_name
        AND value_rel.branch = $target_branch_name
        RETURN attr_val.value AS checksum, (attr_rel.status = "active" AND value_rel.status = "active") AS checksum_is_active
        ORDER BY value_rel.from DESC, attr_rel.from DESC
        LIMIT 1
    }
    // -----------------------
    // get the artifact's storage_id on target branch
    // -----------------------
    CALL {
        WITH target_artifact
        OPTIONAL MATCH (target_artifact)-[attr_rel:HAS_ATTRIBUTE]->(attr:Attribute)-[value_rel:HAS_VALUE]->(attr_val:AttributeValue)
        WHERE attr.name = "storage_id"
        AND attr_rel.branch = $target_branch_name
        AND value_rel.branch = $target_branch_name
        RETURN attr_val.value AS storage_id, (attr_rel.status = "active" AND value_rel.status = "active") AS storage_id_is_active
        ORDER BY value_rel.from DESC, attr_rel.from DESC
        LIMIT 1
    }
    RETURN target_artifact,
    CASE
        WHEN checksum_is_active = TRUE THEN checksum
        ELSE NULL
    END AS target_checksum,
    CASE
        WHEN storage_id_is_active = TRUE THEN storage_id
        ELSE NULL
    END AS target_storage_id
}
        """ % {"artifact_kind": InfrahubKind.ARTIFACT}
        self.return_labels = [
            "source_artifact",
            "target_node",
            "definition_node",
            "source_checksum",
            "source_storage_id",
            "target_checksum",
            "target_storage_id",
        ]
        self.add_to_query(query=query)
