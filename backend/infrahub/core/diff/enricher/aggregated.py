from ..model.path import CalculatedDiffs, EnrichedDiffs
from .interface import DiffEnricherInterface


class AggregatedDiffEnricher:
    def __init__(self, enrichers: list[DiffEnricherInterface]) -> None:
        self.enrichers = enrichers

    async def enrich(self, calculated_diffs: CalculatedDiffs) -> EnrichedDiffs:
        enriched_diffs = EnrichedDiffs.from_calculated_diffs(calculated_diffs=calculated_diffs)

        for enricher in self.enrichers:
            await enricher.enrich(enriched_diff_root=enriched_diffs.base_branch_diff, calculated_diffs=calculated_diffs)
            await enricher.enrich(enriched_diff_root=enriched_diffs.diff_branch_diff, calculated_diffs=calculated_diffs)

        return enriched_diffs
