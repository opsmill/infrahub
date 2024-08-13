from abc import ABC, abstractmethod

from ..model.path import CalculatedDiffs, EnrichedDiffRoot


class DiffEnricherInterface(ABC):
    @abstractmethod
    async def enrich(self, enriched_diff_root: EnrichedDiffRoot, calculated_diffs: CalculatedDiffs) -> None: ...
