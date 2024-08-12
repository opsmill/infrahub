from ..model.path import CalculatedDiffs, EnrichedDiffRoot
from .interface import DiffEnricherInterface


class DiffHierarchyEnricher(DiffEnricherInterface):
    """Add hierarchy and parent/component nodes to diff even if the higher-level nodes are unchanged"""

    async def enrich(self, enriched_diff_root: EnrichedDiffRoot, calculated_diffs: CalculatedDiffs) -> None: ...
