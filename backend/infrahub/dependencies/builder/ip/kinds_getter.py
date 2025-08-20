from infrahub.core.ipam.kinds_getter import IpamKindsGetter
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class IpamKindsGetterDependency(DependencyBuilder[IpamKindsGetter]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> IpamKindsGetter:
        return IpamKindsGetter(db=context.db)
