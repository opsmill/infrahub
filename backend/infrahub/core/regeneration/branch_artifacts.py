from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import InfrahubKind
from infrahub.core.diff.query.artifact import ArtifactDiffQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class BranchArtifactDefinitionFinder:
    """Find the artifact definitions that have an artifact rendered on a branch.

    A value changed back to the target branch's value drops out of the branch diff, so the artifacts rendered
    from the value in between can only be found from the artifacts themselves.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def find(self, source_branch: Branch, target_branch: Branch) -> set[str]:
        artifact_schema = self.db.schema.get(name=InfrahubKind.ARTIFACT, branch=source_branch, duplicate=False)
        query = await ArtifactDiffQuery.init(
            db=self.db,
            branch=source_branch,
            target_branch=target_branch,
            target_rel_identifier=artifact_schema.get_relationship(name="object").get_identifier(),
            definition_rel_identifier=artifact_schema.get_relationship(name="definition").get_identifier(),
        )
        await query.execute(db=self.db)

        definition_ids: set[str] = set()
        for result in query.get_results():
            try:
                definition_node = result.get_node(label="definition_node")
            except ValueError:
                continue
            definition_ids.add(str(definition_node.get("uuid")))
        return definition_ids
