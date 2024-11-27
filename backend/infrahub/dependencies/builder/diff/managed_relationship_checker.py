from infrahub.core.diff.managed_relationship_checker import ManagedRelationshipChecker
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from ..ip.kinds_getter import IpamKindsGetterDependency


class ManagedRelationshipCheckerDependency(DependencyBuilder[ManagedRelationshipChecker]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> ManagedRelationshipChecker:
        return ManagedRelationshipChecker(
            branch=context.branch,
            ipam_kinds_getter=IpamKindsGetterDependency.build(context=context),
        )
