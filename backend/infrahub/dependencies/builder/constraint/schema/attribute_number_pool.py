from infrahub.core.validators.attribute.number_pool import AttributeNumberPoolChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaAttributeNumberPoolConstraintDependency(DependencyBuilder[AttributeNumberPoolChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> AttributeNumberPoolChecker:
        return AttributeNumberPoolChecker(db=context.db, branch=context.branch)
