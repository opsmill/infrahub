from dataclasses import dataclass

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.query.ipam import IPPrefixUtilization
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from .constants import PrefixMemberType
from .size import get_prefix_space


@dataclass
class PrefixChildDetails:
    child_type: PrefixMemberType
    prefixlen: int
    ip_value: str


class PrefixUtilizationGetter:
    def __init__(self, db: InfrahubDatabase, ip_prefixes: list[Node], at: Timestamp | str | None = None) -> None:
        self.db = db
        self.ip_prefixes = ip_prefixes
        self.at = at
        self._has_data = False
        self._results_by_prefix_id: dict[str, dict[str, list[PrefixChildDetails]]] = {}

    async def _fetch_data(self) -> None:
        if self._has_data is False:
            await self._run_and_parse_query()
        self._has_data = True

    async def _run_and_parse_query(self) -> None:
        self._results_by_prefix_id = {}
        query = await IPPrefixUtilization.init(
            db=self.db,
            at=self.at,
            ip_prefixes=self.ip_prefixes,
            allocated_kinds=[InfrahubKind.IPPREFIX, InfrahubKind.IPADDRESS],
        )
        await query.execute(db=self.db)

        for result in query.get_results():
            prefix_node = result.get_node("pfx")
            prefix_id = str(prefix_node.get("uuid"))
            branch_name = str(result.get("branch"))
            child_node = result.get_node("child")
            if InfrahubKind.IPADDRESS in child_node.labels:
                child_type = PrefixMemberType.ADDRESS
            else:
                child_type = PrefixMemberType.PREFIX
            child_value_node = result.get_node("av")
            child_prefixlen = child_value_node.get("prefixlen")
            child_ip_value = child_value_node.get("value")

            if prefix_id not in self._results_by_prefix_id:
                self._results_by_prefix_id[prefix_id] = {}
            if branch_name not in self._results_by_prefix_id[prefix_id]:
                self._results_by_prefix_id[prefix_id][branch_name] = []
            self._results_by_prefix_id[prefix_id][branch_name].append(
                PrefixChildDetails(child_type=child_type, prefixlen=child_prefixlen, ip_value=child_ip_value)
            )

    async def get_children(
        self,
        ip_prefixes: list[Node] | None = None,
        prefix_member_type: PrefixMemberType | None = None,
        branch_names: list[str] | None = None,
    ) -> list[PrefixChildDetails]:
        await self._fetch_data()
        prefix_child_details_list: list[PrefixChildDetails] = []
        if ip_prefixes is None:
            ip_prefixes = self.ip_prefixes
        prefix_ids = {prefix.get_id() for prefix in ip_prefixes}
        prefix_ids &= set(self._results_by_prefix_id.keys())
        if not prefix_ids:
            return prefix_child_details_list
        for prefix_id in prefix_ids:
            child_details_by_branch = self._results_by_prefix_id[prefix_id]
            branch_names_to_check = branch_names or list(child_details_by_branch.keys())
            for branch_name in branch_names_to_check:
                for child_details in child_details_by_branch.get(branch_name, []):
                    if prefix_member_type and child_details.child_type != prefix_member_type:
                        continue
                    prefix_child_details_list.append(child_details)
        return prefix_child_details_list

    async def get_num_children_in_use(
        self,
        ip_prefixes: list[Node] | None = None,
        prefix_member_type: PrefixMemberType | None = None,
        branch_names: list[str] | None = None,
    ) -> int:
        children = await self.get_children(
            ip_prefixes=ip_prefixes, prefix_member_type=prefix_member_type, branch_names=branch_names
        )
        return len(children)

    async def _get_prefix_use_fraction(
        self, ip_prefixes: list[Node] | None = None, branch_names: list[str] | None = None
    ) -> tuple[int, int]:
        total_prefix_space = 0
        total_used_space = 0
        if ip_prefixes is None:
            ip_prefixes = self.ip_prefixes
        for ip_prefix in ip_prefixes:
            total_prefix_space += get_prefix_space(ip_prefix=ip_prefix)
            max_prefixlen = ip_prefix.prefix.obj.max_prefixlen  # type: ignore[attr-defined]
            children = await self.get_children(
                ip_prefixes=[ip_prefix], prefix_member_type=PrefixMemberType.PREFIX, branch_names=branch_names
            )
            for child in children:
                total_used_space += 2 ** (max_prefixlen - child.prefixlen)
        return total_used_space, total_prefix_space

    async def _get_address_use_fraction(
        self, ip_prefixes: list[Node] | None = None, branch_names: list[str] | None = None
    ) -> tuple[int, int]:
        total_prefix_space = 0
        if ip_prefixes is None:
            ip_prefixes = self.ip_prefixes
        for ip_prefix in ip_prefixes:
            total_prefix_space += get_prefix_space(ip_prefix=ip_prefix)
        total_used_space = await self.get_num_children_in_use(
            ip_prefixes=ip_prefixes, prefix_member_type=PrefixMemberType.ADDRESS, branch_names=branch_names
        )
        return total_used_space, total_prefix_space

    async def get_use_percentage(
        self, ip_prefixes: list[Node] | None = None, branch_names: list[str] | None = None
    ) -> float:
        grand_total_used, grand_total_space = 0, 0
        address_prefixes, prefix_prefixes = [], []
        if ip_prefixes is None:
            ip_prefixes = self.ip_prefixes
        for ip_prefix in ip_prefixes:
            if ip_prefix.member_type.value == PrefixMemberType.ADDRESS.value:  # type: ignore[union-attr,attr-defined]
                address_prefixes.append(ip_prefix)
            else:
                prefix_prefixes.append(ip_prefix)
        if address_prefixes:
            address_total_used, address_total_space = await self._get_address_use_fraction(
                ip_prefixes=address_prefixes, branch_names=branch_names
            )
            grand_total_used += address_total_used
            grand_total_space += address_total_space
        if prefix_prefixes:
            prefix_total_used, prefix_total_space = await self._get_prefix_use_fraction(
                ip_prefixes=prefix_prefixes, branch_names=branch_names
            )
            grand_total_used += prefix_total_used
            grand_total_space += prefix_total_space
        if grand_total_space == 0:
            return 0.0
        return (grand_total_used / grand_total_space) * 100
