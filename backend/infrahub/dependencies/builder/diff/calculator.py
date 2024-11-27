from infrahub.core.diff.calculator import DiffCalculator
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from .query_parser import DiffQueryParserDependency


class DiffCalculatorDependency(DependencyBuilder[DiffCalculator]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffCalculator:
        return DiffCalculator(db=context.db, diff_query_parser=DiffQueryParserDependency.build(context=context))
