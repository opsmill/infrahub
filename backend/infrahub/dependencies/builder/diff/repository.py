from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from .deserializer import DiffDeserializerDependency


class DiffRepositoryDependency(DependencyBuilder[DiffRepository]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffRepository:
        return DiffRepository(db=context.db, deserializer=DiffDeserializerDependency.build(context=context))
