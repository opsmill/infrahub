from ..model.path import CalculatedDiffs, EnrichedDiffs, TrackingId
from .interface import DiffEnricherInterface


class AggregatedDiffEnricher:
    def __init__(self, enrichers: list[DiffEnricherInterface]) -> None:
        self.enrichers = enrichers

    async def enrich(self, calculated_diffs: CalculatedDiffs, tracking_id: TrackingId) -> EnrichedDiffs:
        enriched_diffs = EnrichedDiffs.from_calculated_diffs(calculated_diffs=calculated_diffs, tracking_id=tracking_id)

        for enricher in self.enrichers:
            for enriched_diff_root in enriched_diffs.roots:
                await enricher.enrich(enriched_diff_root=enriched_diff_root, calculated_diffs=calculated_diffs)

        return enriched_diffs
