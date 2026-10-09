from infrahub.core.registry import registry
from infrahub.core.validators.pool.scope import NumberPoolScopeChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext
from infrahub.pools.scoped_number_pool_reader import ScopedNumberPoolReader


class SchemaNumberPoolScopeConstraintDependency(DependencyBuilder[NumberPoolScopeChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NumberPoolScopeChecker:
        return NumberPoolScopeChecker(pool_source=ScopedNumberPoolReader(db=context.db), schema_source=registry.schema)
