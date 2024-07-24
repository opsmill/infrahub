from .model.path import EnrichedDiffRoot


class DiffCombiner:
    def combine(self, earlier_diff: EnrichedDiffRoot, later_diff: EnrichedDiffRoot) -> EnrichedDiffRoot:  # pylint: disable=unused-argument
        return earlier_diff
