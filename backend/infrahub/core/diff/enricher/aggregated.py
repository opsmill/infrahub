from uuid import uuid4

from ..model.path import CalculatedDiffs, EnrichedDiffRoot
from .interface import DiffEnricherInterface


class AggregatedDiffEnricher:
    def __init__(self, enrichers: list[DiffEnricherInterface]) -> None:
        self.enrichers = enrichers
        self.conflicts_enricher = None
        self.parent_nodes_enricher = None

    async def enrich(self, calculated_diffs: CalculatedDiffs) -> EnrichedDiffRoot:
        enriched_root = EnrichedDiffRoot(
            base_branch_name=calculated_diffs.base_branch_name,
            diff_branch_name=calculated_diffs.diff_branch_name,
            from_time=calculated_diffs.diff_branch_diff.from_time,
            to_time=calculated_diffs.diff_branch_diff.to_time,
            uuid=str(uuid4()),
            nodes=set(),
        )

        # TODO: fill in the nodes

        for enricher in self.enrichers:
            await enricher.enrich(enriched_diff_root=enriched_root, calculated_diffs=calculated_diffs)

        return enriched_root
