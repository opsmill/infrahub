from typing import Iterable

from infrahub.core.constants import InfrahubKind
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import SchemaNotFoundError


class IpamKindsGetter:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    def get_ipam_address_kinds(self, branch_names: Iterable[str]) -> set[str]:
        ip_address_kinds: set[str] = set()
        for branch_name in branch_names:
            try:
                address_generic_schema_source = self.db.schema.get(
                    InfrahubKind.IPADDRESS, branch=branch_name, duplicate=False
                )
            except SchemaNotFoundError:
                address_generic_schema_source = None
            try:
                address_generic_schema_target = self.db.schema.get(
                    InfrahubKind.IPADDRESS, branch=branch_name, duplicate=False
                )
            except SchemaNotFoundError:
                address_generic_schema_target = None

            ip_address_kinds.update(
                set(
                    getattr(address_generic_schema_target, "used_by", [])
                    + getattr(address_generic_schema_source, "used_by", [])
                )
            )
        return ip_address_kinds

    def get_ipam_prefix_kinds(self, branch_names: Iterable[str]) -> set[str]:
        ip_prefix_kinds: set[str] = set()
        for branch_name in branch_names:
            try:
                prefix_generic_schema_source = self.db.schema.get(
                    InfrahubKind.IPPREFIX, branch=branch_name, duplicate=False
                )
            except SchemaNotFoundError:
                prefix_generic_schema_source = None
            try:
                prefix_generic_schema_target = self.db.schema.get(
                    InfrahubKind.IPPREFIX, branch=branch_name, duplicate=False
                )
            except SchemaNotFoundError:
                prefix_generic_schema_target = None

            ip_prefix_kinds.update(
                set(
                    getattr(prefix_generic_schema_source, "used_by", [])
                    + getattr(prefix_generic_schema_target, "used_by", [])
                )
            )
        return ip_prefix_kinds

    def get_prefix_managed_relationship_names(self) -> set[str]:
        return {"parent", "children", "ip_addresses"}

    def get_address_managed_relationship_names(self) -> set[str]:
        return {"ip_prefix"}
