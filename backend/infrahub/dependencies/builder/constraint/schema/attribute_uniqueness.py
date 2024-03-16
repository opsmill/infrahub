from infrahub.core.validators.attribute.unique import AttributeUniquenessChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaAttributeUniqueConstraintDependency(DependencyBuilder[AttributeUniquenessChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> AttributeUniquenessChecker:
        return AttributeUniquenessChecker(db=context.db, branch=context.branch)
