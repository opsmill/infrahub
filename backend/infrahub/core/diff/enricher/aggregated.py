from ..model.path import CalculatedDiffs, EnrichedDiffRoot
from .interface import DiffEnricherInterface


class AggregatedDiffEnricher:
    def __init__(self, enrichers: list[DiffEnricherInterface]) -> None:
        self.enrichers = enrichers

    async def enrich(self, calculated_diffs: CalculatedDiffs) -> EnrichedDiffRoot:
        enriched_root = EnrichedDiffRoot.from_calculated_diffs(calculated_diffs=calculated_diffs)

        for enricher in self.enrichers:
            await enricher.enrich(enriched_diff_root=enriched_root, calculated_diffs=calculated_diffs)

        return enriched_root
