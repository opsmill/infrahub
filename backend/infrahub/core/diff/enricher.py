from .model.path import CalculatedDiffs, EnrichedDiffRoot


class DiffEnricher:
    def __init__(self) -> None:
        self.conflicts_enricher = None
        self.parent_nodes_enricher = None

    async def enrich(self, calculated_diffs: CalculatedDiffs) -> EnrichedDiffRoot:
        raise NotImplementedError()
