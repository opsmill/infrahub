from infrahub.core.validators.attribute.kind import AttributeKindChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaAttributeKindConstraintDependency(DependencyBuilder[AttributeKindChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> AttributeKindChecker:
        return AttributeKindChecker(db=context.db, branch=context.branch)
