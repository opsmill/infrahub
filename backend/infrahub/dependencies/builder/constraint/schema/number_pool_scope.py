from infrahub.core.registry import registry
from infrahub.core.validators.pool.scope import NumberPoolScopeChecker
from infrahub.core.validators.pool.scope_dependency import DependentPoolFinder, ScopeViolationBuilder
from infrahub.core.validators.schema_branch.number_pool_scope_validator import (
    DeclaredScopeComparator,
    DeclaredScopeValidator,
)
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext
from infrahub.pools.scoped_number_pool_reader import ScopedNumberPoolReader


class SchemaNumberPoolScopeConstraintDependency(DependencyBuilder[NumberPoolScopeChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NumberPoolScopeChecker:
        return NumberPoolScopeChecker(
            pool_source=ScopedNumberPoolReader(db=context.db),
            schema_source=registry.schema,
            pool_finder=DependentPoolFinder(),
            violation_builder=ScopeViolationBuilder(),
            declared_scope_validator=DeclaredScopeValidator(),
            declared_scope_comparator=DeclaredScopeComparator(),
            default_branch_name=registry.default_branch,
        )
