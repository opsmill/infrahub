from dataclasses import dataclass
from itertools import chain
from typing import Optional, Union

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
    def __init__(
        self, db: InfrahubDatabase, ip_prefixes: list[Node], at: Optional[Union[Timestamp, str]] = None
    ) -> None:
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
        query = await IPPrefixUtilization.init(db=self.db, at=self.at, ip_prefixes=self.ip_prefixes)
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

    async def get_children(self, ip_prefix: Node, branch_name: Optional[str] = None) -> list[PrefixChildDetails]:
        await self._fetch_data()
        prefix_id = ip_prefix.get_id()
        if prefix_id not in self._results_by_prefix_id:
            return []
        child_details_by_branch = self._results_by_prefix_id[prefix_id]
        if branch_name:
            children_to_check = child_details_by_branch.get(branch_name, [])
        else:
            children_to_check = list(chain(*child_details_by_branch.values()))
        type_to_check = PrefixMemberType(ip_prefix.member_type.value)  # type: ignore[attr-defined]
        return [child_details for child_details in children_to_check if child_details.child_type == type_to_check]

    async def get_num_children_in_use(self, ip_prefix: Node, branch_name: Optional[str] = None) -> int:
        children = await self.get_children(ip_prefix=ip_prefix, branch_name=branch_name)
        return len(children)

    async def _get_prefix_use_percentage(self, ip_prefix: Node, branch_name: Optional[str] = None) -> float:
        prefix_space = get_prefix_space(ip_prefix=ip_prefix)
        max_prefixlen = ip_prefix.prefix.obj.max_prefixlen  # type: ignore[attr-defined]
        used_space = 0
        children = await self.get_children(ip_prefix=ip_prefix, branch_name=branch_name)
        for child in children:
            used_space += 2 ** (max_prefixlen - child.prefixlen)
        return (used_space / prefix_space) * 100

    async def _get_address_use_percentage(self, ip_prefix: Node, branch_name: Optional[str] = None) -> float:
        prefix_space = get_prefix_space(ip_prefix=ip_prefix)
        return (await self.get_num_children_in_use(ip_prefix=ip_prefix, branch_name=branch_name) / prefix_space) * 100

    async def get_use_percentage(self, ip_prefix: Node, branch_name: Optional[str] = None) -> float:
        if ip_prefix.member_type.value == PrefixMemberType.ADDRESS.value:  # type: ignore[attr-defined]
            return await self._get_address_use_percentage(ip_prefix=ip_prefix, branch_name=branch_name)
        return await self._get_prefix_use_percentage(ip_prefix=ip_prefix, branch_name=branch_name)
