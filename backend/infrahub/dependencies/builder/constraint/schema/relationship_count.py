from infrahub.core.validators.relationship.count import RelationshipCountChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaRelationshipCountConstraintDependency(DependencyBuilder[RelationshipCountChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> RelationshipCountChecker:
        return RelationshipCountChecker(db=context.db, branch=context.branch)
