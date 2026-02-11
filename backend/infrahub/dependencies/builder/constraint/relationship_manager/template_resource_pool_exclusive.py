from infrahub.core.relationship.constraints.template_resource_pool_exclusive import (
    TemplateResourcePoolExclusiveConstraint,
)
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class TemplateResourcePoolExclusiveConstraintDependency(DependencyBuilder[TemplateResourcePoolExclusiveConstraint]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> TemplateResourcePoolExclusiveConstraint:
        return TemplateResourcePoolExclusiveConstraint(db=context.db, branch=context.branch)
