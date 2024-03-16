from infrahub.core.validators.uniqueness.checker import UniquenessChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaUniquenessConstraintDependency(DependencyBuilder[UniquenessChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> UniquenessChecker:
        return UniquenessChecker(db=context.db, branch=context.branch)
