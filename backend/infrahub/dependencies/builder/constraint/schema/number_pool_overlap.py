from infrahub.core.validators.pool.overlap import UniqueAttributePoolOverlapChecker
from infrahub.core.validators.pool.scope_dependency import ScopeViolationBuilder
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext
from infrahub.pools.number_pool_repository import NumberPoolRepository


class SchemaNumberPoolOverlapConstraintDependency(DependencyBuilder[UniqueAttributePoolOverlapChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> UniqueAttributePoolOverlapChecker:
        return UniqueAttributePoolOverlapChecker(
            pool_reader=NumberPoolRepository(db=context.db), violation_builder=ScopeViolationBuilder()
        )
