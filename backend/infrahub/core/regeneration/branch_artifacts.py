from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import InfrahubKind
from infrahub.core.query import Query, QueryType

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class BranchRenderedArtifactDefinitionsQueryResult:
    definition_id: str


class BranchRenderedArtifactDefinitionsQuery(Query):
    """Return the definitions of the artifacts whose checksum was written on the query branch."""

    name = "branch-rendered-artifact-definitions"
    type = QueryType.READ

    def __init__(self, definition_rel_identifier: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.definition_rel_identifier = definition_rel_identifier

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)
        self.params["branch_name"] = self.branch.name
        self.params["definition_rel_identifier"] = self.definition_rel_identifier

        # Starting from the values written on the branch keeps the cost proportional to the branch's changes.
        query = """
MATCH (artifact:%(artifact_kind)s)-[:HAS_ATTRIBUTE]->(:Attribute {name: "checksum"})
    -[:HAS_VALUE {branch: $branch_name}]->(:AttributeValue)
WITH DISTINCT artifact
CALL (artifact) {
    MATCH (artifact)-[r1:IS_RELATED]-(:Relationship {name: $definition_rel_identifier})-[r2:IS_RELATED]-(definition:Node)
    WHERE all(r IN [r1, r2] WHERE (%(branch_filter)s))
    RETURN definition, r1.status = "active" AND r2.status = "active" AS is_active
    ORDER BY r1.branch_level DESC, r2.branch_level DESC, r1.from DESC, r2.from DESC, r1.status ASC, r2.status ASC
    LIMIT 1
}
WITH definition, is_active
WHERE is_active
WITH DISTINCT definition.uuid AS definition_id
        """ % {"artifact_kind": InfrahubKind.ARTIFACT, "branch_filter": branch_filter}
        self.add_to_query(query)
        self.return_labels = ["definition_id"]
        self.order_by = ["definition_id"]

    def get_data(self) -> Generator[BranchRenderedArtifactDefinitionsQueryResult]:
        for result in self.get_results():
            yield BranchRenderedArtifactDefinitionsQueryResult(definition_id=result.get_as_type("definition_id", str))


class BranchArtifactDefinitionFinder:
    """Find the artifact definitions that have an artifact rendered on a branch.

    A value changed back to the target branch's value drops out of the branch diff, so the artifacts rendered
    from the value in between can only be found from the artifacts themselves.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def find(self, branch: Branch) -> set[str]:
        artifact_schema = self.db.schema.get(name=InfrahubKind.ARTIFACT, branch=branch, duplicate=False)
        query = await BranchRenderedArtifactDefinitionsQuery.init(
            db=self.db,
            branch=branch,
            definition_rel_identifier=artifact_schema.get_relationship(name="definition").get_identifier(),
        )
        await query.execute(db=self.db)
        return {result.definition_id for result in query.get_data()}
