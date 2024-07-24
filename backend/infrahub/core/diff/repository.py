from infrahub.core.branch import Branch
from infrahub.core.timestamp import Timestamp

from .model.path import EnrichedDiffRoot


class DiffRepository:
    async def get(
        self, base_branch: Branch, diff_branch: Branch, from_time: Timestamp, to_time: Timestamp
    ) -> list[EnrichedDiffRoot]:
        """Get all diffs for the given branch that touch the given timeframe in chronological order"""
        raise NotImplementedError()

    async def save(self, enriched_diff: EnrichedDiffRoot) -> None:  # pylint: disable=unused-argument
        """
        Cached Diff Graph Format
        (DiffRoot)-[DIFF_HAS_NODE]->(DiffNode)
            (DiffNode)-[DIFF_HAS_ATTRIBUTE]->(DiffAttribute)
                (DiffAttribute)-[DIFF_HAS_PROPERTY]->(DiffProperty)
                    (DiffProperty)-[DIFF_HAS_CONFLICT]->(DiffConflict)

            (DiffNode)-[DIFF_HAS_RELATIONSHIP]->(DiffRelationship)
                (DiffRelationship)-[DIFF_HAS_NODE]->(DiffNode)
                (DiffRelationship)-[DIFF_HAS_ELEMENT]->(DiffRelationshipElement)
                    (DiffRelationshipElement)-[DIFF_HAS_PROPERTY]->(DiffProperty)
                        (DiffProperty)-[DIFF_HAS_CONFLICT]->(DiffConflict)
        """
