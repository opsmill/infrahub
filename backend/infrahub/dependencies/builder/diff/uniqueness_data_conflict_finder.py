from infrahub.core.diff.uniqueness_data_conflict_finder import DiffUniquenessDataConflictFinder
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from ..constraint.schema.uniqueness import SchemaUniquenessConstraintDependency


class DiffUniquenessDataConflictFinderDependency(DependencyBuilder[DiffUniquenessDataConflictFinder]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffUniquenessDataConflictFinder:
        return DiffUniquenessDataConflictFinder(
            db=context.db, uniqueness_checker=SchemaUniquenessConstraintDependency.build(context=context)
        )
