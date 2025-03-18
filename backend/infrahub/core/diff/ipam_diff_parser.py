from dataclasses import dataclass

from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.ipam.kinds_getter import IpamKindsGetter
from infrahub.core.ipam.model import IpamNodeDetails
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase

from .model.path import EnrichedDiffNode
from .repository.repository import DiffRepository


@dataclass
class ChangedIpamNodeDetails:
    node_uuid: str
    is_address: bool
    is_delete: bool
    namespace_id: str | None
    ip_value: str | None


class IpamDiffParser:
    def __init__(
        self,
        db: InfrahubDatabase,
        diff_repository: DiffRepository,
        ip_kinds_getter: IpamKindsGetter,
    ) -> None:
        self.db = db
        self.diff_repo = diff_repository
        self.ip_kinds_getter = ip_kinds_getter

    async def get_changed_ipam_node_details(
        self, source_branch_name: str, target_branch_name: str
    ) -> list[IpamNodeDetails]:
        ip_address_kinds = await self.ip_kinds_getter.get_ipam_address_kinds(
            branch_names=[source_branch_name, target_branch_name]
        )
        ip_prefix_kinds = await self.ip_kinds_getter.get_ipam_prefix_kinds(
            branch_names=[source_branch_name, target_branch_name]
        )
        if not ip_address_kinds and not ip_prefix_kinds:
            return []

        enriched_diffs = await self.diff_repo.get(
            base_branch_name=target_branch_name,
            diff_branch_names=[source_branch_name],
            tracking_id=BranchTrackingId(name=source_branch_name),
            filters={
                "kind": {"includes": list(ip_address_kinds | ip_prefix_kinds)},
                "status": {"excludes": {DiffAction.UNCHANGED}},
            },
        )
        changed_node_details: list[ChangedIpamNodeDetails] = []
        for diff in enriched_diffs:
            for node_diff in diff.nodes:
                if node_diff.action is DiffAction.UNCHANGED:
                    continue
                if node_diff.kind in ip_address_kinds:
                    is_address = True
                elif node_diff.kind in ip_prefix_kinds:
                    is_address = False
                else:
                    continue
                ip_value = self._get_ip_value(node_diff=node_diff)
                namespace_id = self._get_namespace_id(node_diff=node_diff)
                changed_node_details.append(
                    ChangedIpamNodeDetails(
                        node_uuid=node_diff.uuid,
                        is_delete=node_diff.action is DiffAction.REMOVED,
                        is_address=is_address,
                        namespace_id=namespace_id,
                        ip_value=ip_value,
                    )
                )
        await self._add_missing_values(
            source_branch_name=source_branch_name,
            target_branch_name=target_branch_name,
            changed_node_details=changed_node_details,
        )

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

    async def _add_missing_values_branch(
        self, branch_name: str, changed_node_details: list[ChangedIpamNodeDetails], uuids_missing_data: set[str]
    ) -> None:
        nodes = await NodeManager.get_many(
            db=self.db, branch=branch_name, ids=list(uuids_missing_data), prefetch_relationships=True
        )

        for cnd in changed_node_details:
            if cnd.ip_value and cnd.namespace_id:
                continue
            node_from_db = nodes.get(cnd.node_uuid)
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
            if cnd.ip_value and cnd.namespace_id and cnd.node_uuid in uuids_missing_data:
                uuids_missing_data.remove(cnd.node_uuid)

    async def _add_missing_values(
        self, source_branch_name: str, target_branch_name: str, changed_node_details: list[ChangedIpamNodeDetails]
    ) -> None:
        uuids_missing_data = {
            cnd.node_uuid for cnd in changed_node_details if cnd.ip_value is None or cnd.namespace_id is None
        }
        if not uuids_missing_data:
            return

        await self._add_missing_values_branch(
            branch_name=source_branch_name,
            changed_node_details=changed_node_details,
            uuids_missing_data=uuids_missing_data,
        )
        if not uuids_missing_data:
            return

        await self._add_missing_values_branch(
            branch_name=target_branch_name,
            changed_node_details=changed_node_details,
            uuids_missing_data=uuids_missing_data,
        )

    def _get_ip_value(self, node_diff: EnrichedDiffNode) -> str | None:
        ip_attr_diff = None
        for diff_attr in node_diff.attributes:
            if diff_attr.name in {"prefix", "address"}:
                ip_attr_diff = diff_attr
                break
        if not ip_attr_diff:
            return None
        for diff_property in ip_attr_diff.properties:
            if diff_property.property_type is DatabaseEdgeType.HAS_VALUE:
                return diff_property.new_value or diff_property.previous_value
        return None

    def _get_namespace_id(self, node_diff: EnrichedDiffNode) -> str | None:
        namespace_rel = None
        for diff_rel in node_diff.relationships:
            if diff_rel.name == "ip_namespace":
                namespace_rel = diff_rel
                break
        if not namespace_rel or not namespace_rel.relationships:
            return None
        namespace_rel_element = next(iter(namespace_rel.relationships))
        return namespace_rel_element.peer_id
