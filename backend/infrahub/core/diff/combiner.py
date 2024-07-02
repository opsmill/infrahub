from .model.path import DiffRoot


class DiffCombiner:
    def combine(self, earlier_diff: DiffRoot, later_diff: DiffRoot) -> DiffRoot:  # pylint: disable=unused-argument
        return earlier_diff
