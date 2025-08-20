from infrahub.core.relationship.constraints.profiles_kind import RelationshipProfilesKindConstraint
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class RelationshipProfilesKindConstraintDependency(DependencyBuilder[RelationshipProfilesKindConstraint]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> RelationshipProfilesKindConstraint:
        return RelationshipProfilesKindConstraint(db=context.db, branch=context.branch)
