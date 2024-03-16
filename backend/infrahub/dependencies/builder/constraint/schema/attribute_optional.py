from infrahub.core.validators.attribute.optional import AttributeOptionalChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaAttributeOptionalConstraintDependency(DependencyBuilder[AttributeOptionalChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> AttributeOptionalChecker:
        return AttributeOptionalChecker(db=context.db, branch=context.branch)
