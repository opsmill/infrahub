from infrahub.core.registry import registry
from infrahub.core.validators.pool.rename import NumberPoolRenameChecker
from infrahub.core.validators.pool.scope_dependency import ScopeViolationBuilder
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext
from infrahub.pools.scoped_number_pool_reader import ScopedNumberPoolReader


class SchemaNumberPoolRenameConstraintDependency(DependencyBuilder[NumberPoolRenameChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NumberPoolRenameChecker:
        return NumberPoolRenameChecker(
            pool_source=ScopedNumberPoolReader(db=context.db),
            schema_source=registry.schema,
            violation_builder=ScopeViolationBuilder(),
        )
