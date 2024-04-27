from dataclasses import dataclass
from typing import Optional

from infrahub.core import registry
from infrahub.core.constants import DiffAction, InfrahubKind
from infrahub.core.constants.relationship_label import RELATIONSHIP_TO_VALUE_LABEL
from infrahub.core.diff.branch_differ import BranchDiffer
from infrahub.core.diff.model import NodeDiffElement, RelationshipDiffElement
from infrahub.core.ipam.model import IpamNodeDetails
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase


@dataclass
class ChangedIpamNodeDetails:
    node_uuid: str
    is_address: bool
    is_delete: bool
    namespace_id: Optional[str]
    ip_value: Optional[str]


class IpamDiffParser:
    def __init__(
        self, differ: BranchDiffer, source_branch_name: str, target_branch_name: str, db: InfrahubDatabase
    ) -> None:
        self.source_branch_name = source_branch_name
        self.target_branch_name = target_branch_name
        self.differ = differ
        self.db = db

    async def get_changed_ipam_node_details(self) -> list[IpamNodeDetails]:
        prefix_generic_schema_source = registry.schema.get(
            InfrahubKind.IPPREFIX, branch=self.source_branch_name, duplicate=False
        )
        prefix_generic_schema_target = registry.schema.get(
            InfrahubKind.IPPREFIX, branch=self.target_branch_name, duplicate=False
        )
        address_generic_schema_source = registry.schema.get(
            InfrahubKind.IPADDRESS, branch=self.source_branch_name, duplicate=False
        )
        address_generic_schema_target = registry.schema.get(
            InfrahubKind.IPADDRESS, branch=self.target_branch_name, duplicate=False
        )

        ip_address_kinds = set(
            getattr(address_generic_schema_target, "used_by", [])
            + getattr(address_generic_schema_source, "used_by", [])
        )
        ip_prefix_kinds = set(
            getattr(prefix_generic_schema_target, "used_by", []) + getattr(prefix_generic_schema_source, "used_by", [])
        )
        if not ip_address_kinds and not ip_prefix_kinds:
            return []

        node_diffs_by_branch = await self.differ.get_nodes()
        rel_diffs_by_branch = await self.differ.get_relationships_per_node()
        changed_node_details = []
        for branch in node_diffs_by_branch:
            node_diffs_by_id = node_diffs_by_branch[branch]
            rel_diffs_by_node_id = rel_diffs_by_branch.get(branch, {})
            for node_id, diff_element in node_diffs_by_id.items():
                if diff_element.kind in ip_address_kinds:
                    is_address = True
                elif diff_element.kind in ip_prefix_kinds:
                    is_address = False
                else:
                    continue
                rel_diffs_for_node = rel_diffs_by_node_id.get(node_id)
                ip_value = self._get_ip_value(diff_element)
                namespace_id = None
                if rel_diffs_for_node:
                    namespace_id = self._get_namespace_id(rel_diffs_for_node)
                changed_node_details.append(
                    ChangedIpamNodeDetails(
                        node_uuid=node_id,
                        is_delete=diff_element.action is DiffAction.REMOVED,
                        is_address=is_address,
                        namespace_id=namespace_id,
                        ip_value=ip_value,
                    )
                )
                await self._add_missing_values(branch=branch, changed_node_details=changed_node_details)

        return [
            IpamNodeDetails(
                node_uuid=cnd.node_uuid,
                is_delete=cnd.is_delete,
                is_address=cnd.is_address,
                namespace_id=cnd.namespace_id,
                ip_value=cnd.ip_value,
            )
            for cnd in changed_node_details
            if cnd.namespace_id and cnd.ip_value
        ]

    async def _add_missing_values(self, branch: str, changed_node_details: list[ChangedIpamNodeDetails]) -> None:
        uuids_missing_data = [
            cnd.node_uuid for cnd in changed_node_details if cnd.ip_value is None or cnd.namespace_id is None
        ]
        if not uuids_missing_data:
            return

        nodes_on_branch = await NodeManager.get_many(
            db=self.db, branch=branch, ids=uuids_missing_data, prefetch_relationships=True
        )

        for cnd in changed_node_details:
            if cnd.ip_value and cnd.namespace_id:
                continue
            node_from_db = nodes_on_branch.get(cnd.node_uuid)
            if not node_from_db:
                continue
            if not cnd.ip_value:
                if cnd.is_address and hasattr(node_from_db, "address"):
                    cnd.ip_value = node_from_db.address.value
                elif not cnd.is_address and hasattr(node_from_db, "prefix"):
                    cnd.ip_value = node_from_db.prefix.value
            if not cnd.namespace_id:
                rels = await node_from_db.ip_namespace.get_relationships(db=self.db)  # type: ignore[attr-defined]
                if rels:
                    cnd.namespace_id = rels[0].get_peer_id()

    def _get_ip_value(self, node_diff: NodeDiffElement) -> Optional[str]:
        if "prefix" in node_diff.attributes:
            attr_element = node_diff.attributes["prefix"]
        elif "address" in node_diff.attributes:
            attr_element = node_diff.attributes["address"]
        else:
            return None
        if RELATIONSHIP_TO_VALUE_LABEL not in attr_element.properties:
            return None
        value_element = attr_element.properties[RELATIONSHIP_TO_VALUE_LABEL].value
        if not value_element:
            return None
        return value_element.new or value_element.previous

    def _get_namespace_id(self, rel_diffs_for_node: dict[str, list[RelationshipDiffElement]]) -> Optional[str]:
        if "ip_namespace__ip_prefix" in rel_diffs_for_node:
            rel_elements = rel_diffs_for_node["ip_namespace__ip_prefix"]
        elif "ip_namespace__ip_address" in rel_diffs_for_node:
            rel_elements = rel_diffs_for_node["ip_namespace__ip_address"]
        else:
            return None
        if not rel_elements:
            return None
        for rel in rel_elements[0].nodes.values():
            if InfrahubKind.IPNAMESPACE in rel.labels:
                return rel.id
        return None
