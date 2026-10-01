from infrahub.core.diff.model.path import EnrichedDiffRoot, TrackingId
from infrahub.core.diff.query.filters import EnrichedDiffQueryFilters
from infrahub.core.diff.repository.repository import DiffRepository


class RecordingDiffRepository(DiffRepository):
    """DiffRepository that records the (branch name, diff id) of every single diff it loads with its nodes."""

    def __init__(self, repository: DiffRepository) -> None:
        super().__init__(
            db=repository.db, deserializer=repository.deserializer, max_save_batch_size=repository.max_save_batch_size
        )
        self.loaded_diffs: list[tuple[str, str | None]] = []

    async def get_one(
        self,
        diff_branch_name: str,
        tracking_id: TrackingId | None = None,
        diff_id: str | None = None,
        filters: EnrichedDiffQueryFilters | None = None,
        include_parents: bool = True,
    ) -> EnrichedDiffRoot:
        self.loaded_diffs.append((diff_branch_name, diff_id))
        return await super().get_one(
            diff_branch_name=diff_branch_name,
            tracking_id=tracking_id,
            diff_id=diff_id,
            filters=filters,
            include_parents=include_parents,
        )
