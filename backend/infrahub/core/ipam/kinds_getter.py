from typing import Iterable

from infrahub.core.constants import InfrahubKind
from infrahub.database import InfrahubDatabase


class IpamKindsGetter:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def get_ipam_address_kinds(self, branch_names: Iterable[str]) -> set[str]:
        ip_address_kinds: set[str] = set()
        for branch_name in branch_names:
            address_generic_schema_source = self.db.schema.get(
                InfrahubKind.IPADDRESS, branch=branch_name, duplicate=False
            )
            address_generic_schema_target = self.db.schema.get(
                InfrahubKind.IPADDRESS, branch=branch_name, duplicate=False
            )

            ip_address_kinds.update(
                set(
                    getattr(address_generic_schema_target, "used_by", [])
                    + getattr(address_generic_schema_source, "used_by", [])
                )
            )
        return ip_address_kinds

    async def get_ipam_prefix_kinds(self, branch_names: Iterable[str]) -> set[str]:
        ip_prefix_kinds: set[str] = set()
        for branch_name in branch_names:
            prefix_generic_schema_source = self.db.schema.get(
                InfrahubKind.IPPREFIX, branch=branch_name, duplicate=False
            )
            prefix_generic_schema_target = self.db.schema.get(
                InfrahubKind.IPPREFIX, branch=branch_name, duplicate=False
            )

            ip_prefix_kinds.update(
                set(
                    getattr(prefix_generic_schema_source, "used_by", [])
                    + getattr(prefix_generic_schema_target, "used_by", [])
                )
            )
        return ip_prefix_kinds
