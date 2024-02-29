from infrahub.core.validators.attribute.length import AttributeLengthChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaAttributLengthConstraintDependency(DependencyBuilder[AttributeLengthChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> AttributeLengthChecker:
        return AttributeLengthChecker(db=context.db, branch=context.branch)
