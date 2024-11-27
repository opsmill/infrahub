from infrahub.core.diff.query_parser import DiffQueryParser
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from .managed_relationship_checker import ManagedRelationshipCheckerDependency


class DiffQueryParserDependency(DependencyBuilder[DiffQueryParser]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffQueryParser:
        return DiffQueryParser(
            db=context.db, managed_relationship_checker=ManagedRelationshipCheckerDependency.build(context=context)
        )
