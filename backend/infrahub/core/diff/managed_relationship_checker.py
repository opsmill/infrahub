from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.ipam.kinds_getter import IpamKindsGetter


class ManagedRelationshipChecker:
    def __init__(
        self,
        ipam_kinds_getter: IpamKindsGetter,
        branch: Branch,
    ) -> None:
        self.ipam_kinds_getter = ipam_kinds_getter
        self.branch = branch
        self._ip_address_kinds: set[str] = set()
        self._ip_prefix_kinds: set[str] = set()
        self._ip_address_managed_rel_names: set[str] = set()
        self._ip_prefix_managed_rel_names: set[str] = set()

    def reset(self) -> None:
        self._ip_address_kinds = self.ipam_kinds_getter.get_ipam_address_kinds(
            branch_names=[registry.default_branch, self.branch.name]
        )
        self._ip_prefix_kinds = self.ipam_kinds_getter.get_ipam_prefix_kinds(
            branch_names=[registry.default_branch, self.branch.name]
        )
        self._ip_address_managed_rel_names = self.ipam_kinds_getter.get_address_managed_relationship_names()
        self._ip_prefix_managed_rel_names = self.ipam_kinds_getter.get_prefix_managed_relationship_names()

    def check(self, node_kind: str, relationship_name: str) -> bool:
        is_prefix_kind = node_kind in self._ip_prefix_kinds
        is_address_kind = node_kind in self._ip_address_kinds
        if not is_prefix_kind and not is_address_kind:
            return False
        if is_prefix_kind:
            return relationship_name in self._ip_prefix_managed_rel_names
        if is_address_kind:
            return relationship_name in self._ip_address_managed_rel_names
        return False
