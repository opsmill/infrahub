from dataclasses import dataclass

from infrahub.core.branch import Branch
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
    """Counts allocations visible from a single branch.

    Use one instance per branch and combine the results externally if a
    cross-branch comparison is required.
    """

    def __init__(
        self, db: InfrahubDatabase, ip_prefixes: list[Node], branch: Branch, at: Timestamp | str | None = None
    ) -> None:
        self.db = db
        self.ip_prefixes = ip_prefixes
        self.branch = branch
        self.at = at
        self._has_data = False
        self._results_by_prefix_id: dict[str, list[PrefixChildDetails]] = {}

    async def _fetch_data(self) -> None:
        if self._has_data:
            return
        query = await IPPrefixUtilization.init(
            db=self.db,
            at=self.at,
            branch=self.branch,
            ip_prefixes=self.ip_prefixes,
            allocated_kinds=[InfrahubKind.IPPREFIX, InfrahubKind.IPADDRESS],
        )
        await query.execute(db=self.db)

        results: dict[str, list[PrefixChildDetails]] = {}
        for item in query.get_data():
            child_type = (
                PrefixMemberType.ADDRESS if InfrahubKind.IPADDRESS in item.child_labels else PrefixMemberType.PREFIX
            )
            results.setdefault(item.prefix_uuid, []).append(
                PrefixChildDetails(child_type=child_type, prefixlen=item.prefixlen, ip_value=item.ip_value)
            )
        self._results_by_prefix_id = results
        self._has_data = True

    async def get_children(
        self,
        ip_prefixes: list[Node] | None = None,
        prefix_member_type: PrefixMemberType | None = None,
    ) -> list[PrefixChildDetails]:
        await self._fetch_data()
        if ip_prefixes is None:
            ip_prefixes = self.ip_prefixes
        result: list[PrefixChildDetails] = []
        for prefix in ip_prefixes:
            for child in self._results_by_prefix_id.get(prefix.get_id(), []):
                if prefix_member_type and child.child_type != prefix_member_type:
                    continue
                result.append(child)
        return result

    async def get_num_children_in_use(
        self,
        ip_prefixes: list[Node] | None = None,
        prefix_member_type: PrefixMemberType | None = None,
    ) -> int:
        children = await self.get_children(ip_prefixes=ip_prefixes, prefix_member_type=prefix_member_type)
        return len(children)

    async def _get_prefix_use_fraction(self, ip_prefixes: list[Node]) -> tuple[int, int]:
        total_prefix_space = 0
        total_used_space = 0
        for ip_prefix in ip_prefixes:
            total_prefix_space += get_prefix_space(ip_prefix=ip_prefix)
            max_prefixlen = ip_prefix.prefix.obj.max_prefixlen  # type: ignore[attr-defined]
            children = await self.get_children(ip_prefixes=[ip_prefix], prefix_member_type=PrefixMemberType.PREFIX)
            for child in children:
                total_used_space += 2 ** (max_prefixlen - child.prefixlen)
        return total_used_space, total_prefix_space

    async def _get_address_use_fraction(self, ip_prefixes: list[Node]) -> tuple[int, int]:
        total_prefix_space = sum(get_prefix_space(ip_prefix=ip_prefix) for ip_prefix in ip_prefixes)
        total_used_space = await self.get_num_children_in_use(
            ip_prefixes=ip_prefixes, prefix_member_type=PrefixMemberType.ADDRESS
        )
        return total_used_space, total_prefix_space

    async def get_use_percentage(self, ip_prefixes: list[Node] | None = None) -> float:
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
            address_total_used, address_total_space = await self._get_address_use_fraction(ip_prefixes=address_prefixes)
            grand_total_used += address_total_used
            grand_total_space += address_total_space
        if prefix_prefixes:
            prefix_total_used, prefix_total_space = await self._get_prefix_use_fraction(ip_prefixes=prefix_prefixes)
            grand_total_used += prefix_total_used
            grand_total_space += prefix_total_space
        if grand_total_space == 0:
            return 0.0
        return min((grand_total_used / grand_total_space) * 100, 100)
