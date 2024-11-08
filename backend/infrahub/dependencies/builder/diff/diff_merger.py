from infrahub.core import registry
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.merger.serializer import DiffMergeSerializer
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from .repository import DiffRepositoryDependency


class DiffMergerDependency(DependencyBuilder[DiffMerger]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> DiffMerger:
        return DiffMerger(
            db=context.db,
            source_branch=context.branch,
            destination_branch=registry.get_branch_from_registry(),
            diff_repository=DiffRepositoryDependency.build(context=context),
            serializer=DiffMergeSerializer(db=context.db, max_batch_size=100),
        )
