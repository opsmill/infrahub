from infrahub.core.validators.relationship.optional import RelationshipOptionalChecker

from ....interface import DependencyBuilder, DependencyBuilderContext


class SchemaRelationshipOptionalConstraintDependency(DependencyBuilder[RelationshipOptionalChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> RelationshipOptionalChecker:
        return RelationshipOptionalChecker(db=context.db, branch=context.branch)
