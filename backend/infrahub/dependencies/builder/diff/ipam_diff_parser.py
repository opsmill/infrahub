from infrahub.core.diff.ipam_diff_parser import IpamDiffParser
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext

from ..ip.kinds_getter import IpamKindsGetterDependency
from .repository import DiffRepositoryDependency


class IpamDiffParserDependency(DependencyBuilder[IpamDiffParser]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> IpamDiffParser:
        return IpamDiffParser(
            db=context.db,
            diff_repository=DiffRepositoryDependency.build(context=context),
            ip_kinds_getter=IpamKindsGetterDependency.build(context=context),
        )
