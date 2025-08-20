from infrahub.core.diff.calculator import DiffCalculator
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffCalculatorDependency(DependencyBuilder[DiffCalculator]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffCalculator:
        return DiffCalculator(db=context.db)
