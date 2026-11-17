from infrahub.core.validators.attribute.min_max import AttributeNumberChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaAttributeNumberConstraintDependency(DependencyBuilder[AttributeNumberChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> AttributeNumberChecker:
        return AttributeNumberChecker(db=context.db, branch=context.branch)
