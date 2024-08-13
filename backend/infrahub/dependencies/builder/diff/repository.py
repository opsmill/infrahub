from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DiffRepositoryDependency(DependencyBuilder[DiffRepository]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffRepository:
        return DiffRepository(db=context.db)
