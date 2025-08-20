from infrahub.core.validators.node.generate_profile import NodeGenerateProfileChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class SchemaGenerateProfileConstraintDependency(DependencyBuilder[NodeGenerateProfileChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> NodeGenerateProfileChecker:
        return NodeGenerateProfileChecker(db=context.db, branch=context.branch)
