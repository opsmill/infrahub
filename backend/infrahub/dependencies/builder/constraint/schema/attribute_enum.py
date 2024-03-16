from infrahub.core.validators.attribute.enum import AttributeEnumChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaAttributeEnumConstraintDependency(DependencyBuilder[AttributeEnumChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> AttributeEnumChecker:
        return AttributeEnumChecker(db=context.db, branch=context.branch)
