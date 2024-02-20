from infrahub.core.validators.attribute.regex import AttributeRegexChecker

from ....interface import DependencyBuilder, DependencyBuilderContext


class SchemaAttributeRegexConstraintDependency(DependencyBuilder[AttributeRegexChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> AttributeRegexChecker:
        return AttributeRegexChecker(db=context.db, branch=context.branch)
