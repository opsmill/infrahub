from infrahub.core.validators.attribute.choices import AttributeChoicesChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaAttributeChoicesConstraintDependency(DependencyBuilder[AttributeChoicesChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> AttributeChoicesChecker:
        return AttributeChoicesChecker(db=context.db, branch=context.branch)
