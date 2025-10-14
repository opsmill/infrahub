from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.progress import Progress

from infrahub.core.branch.models import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import initialization
from infrahub.core.ipam.reconciler import IpamReconciler
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.lock import initialize_lock
from infrahub.log import get_logger

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.core.ipam.constants import AllIPTypes
    from infrahub.database import InfrahubDatabase

log = get_logger()


@dataclass
class IpNodeDetails:
    branch: str
    ip_value: AllIPTypes
    namespace: str
    node_uuid: str


class FindNodesToReconcileQuery(Query):
    name = "find_nodes_to_reconcile_query"
    type = QueryType.READ
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params.update(
            {
                "prefix_kind": InfrahubKind.IPPREFIX,
                "address_kind": InfrahubKind.IPADDRESS,
                "prefix_attribute_name": "prefix",
                "address_attribute_name": "address",
                "attr_names": ["prefix", "address"],
                "namespace_relationship_names": ["ip_namespace__ip_prefix", "ip_namespace__ip_address"],
            }
        )
        query = """
MATCH (root:Root)
LIMIT 1
WITH root.default_branch AS default_branch
// ------------------
// find prefixes and addresses that exist on the default branch
// ------------------
MATCH (ip_node:%(prefix_kind)s|%(address_kind)s)-[e:IS_PART_OF {branch: default_branch, status: "active"}]->(:Root)
WHERE e.to IS NULL
AND NOT exists((ip_node)-[:IS_PART_OF {branch: default_branch, status: "deleted"}]->(:Root))
// ------------------
// check if this node has its prefix/address updated on a branch (or branches)
// ------------------
CALL (ip_node, default_branch) {
    OPTIONAL MATCH (ip_node)-[:HAS_ATTRIBUTE {branch: default_branch, status: "active"}]->
        (attr:Attribute)-[has_value_e:HAS_VALUE {status: "active"}]->(attr_val)
    WHERE attr.name IN $attr_names
    AND has_value_e.branch_level = 2
    AND (
        ($prefix_kind IN labels(ip_node) AND attr.name = $prefix_attribute_name)
        OR ($address_kind IN labels(ip_node) AND attr.name = $address_attribute_name)
    )
    RETURN collect(DISTINCT has_value_e.branch) AS attr_update_branches
}
CALL (ip_node, default_branch) {
    OPTIONAL MATCH (ip_node)-[:IS_RELATED {status: "active"}]-
        (rel:Relationship)-[e2:IS_RELATED {status: "active"}]-(peer:Node)
    WHERE rel.name IN $namespace_relationship_names
    AND e2.branch_level = 2
    RETURN collect(DISTINCT e2.branch) AS namespace_update_branches
}
// ------------------
// filter to only those prefixes/addresses with an update that we care about on a branch
// ------------------
WITH DISTINCT ip_node, default_branch, attr_update_branches, namespace_update_branches
WHERE size(attr_update_branches) > 0 OR size(namespace_update_branches) > 0
// ------------------
// deduplicate branch lists and return one row for each branch
// ------------------
CALL (attr_update_branches, namespace_update_branches) {
    UNWIND attr_update_branches + namespace_update_branches AS branch
    RETURN DISTINCT branch
}
WITH default_branch, branch, ip_node
// ------------------
// confirm node is still active on this branch
// ------------------
MATCH (ip_node)
WHERE NOT exists((ip_node)-[:IS_PART_OF {branch: branch, status: "deleted"}]->(:Root))
// ------------------
// get branched_from time for each branch
// ------------------
CALL (branch) {
    MATCH (b:Branch {name: branch})
    RETURN b.branched_from AS branched_from
}
// ------------------
// get latest namespace on this branch
// ------------------
CALL (default_branch, branch, branched_from, ip_node) {
    MATCH (ip_node)-[e1:IS_RELATED]-(rel:Relationship)-[e2:IS_RELATED]-(peer:%(namespace_kind)s)
    WHERE rel.name IN $namespace_relationship_names
    AND (
        e1.branch = branch
        OR (e1.branch = default_branch AND e1.from < branched_from)
    )
    AND e1.to IS NULL
    AND (
        e2.branch = branch
        OR (e2.branch = default_branch AND e2.from < branched_from)
    )
    AND e2.to IS NULL
    WITH peer, e1.status = "active" AND e2.status = "active" AS is_active
    ORDER BY e2.branch_level DESC, e2.from DESC, e2.status ASC, e1.branch_level DESC, e1.from DESC, e1.status ASC
    LIMIT 1
    WITH peer
    WHERE is_active = TRUE
    RETURN peer.uuid AS namespace_uuid
}
// ------------------
// get latest prefix/address value on this branch
// ------------------
CALL (default_branch, branch, branched_from, ip_node) {
    MATCH (ip_node)-[e1:HAS_ATTRIBUTE]->(attr:Attribute)-[e2:HAS_VALUE]->(av)
    WHERE attr.name IN $attr_names
    AND (
        ($prefix_kind IN labels(ip_node) AND attr.name = $prefix_attribute_name)
        OR ($address_kind IN labels(ip_node) AND attr.name = $address_attribute_name)
    )
    AND (
        e1.branch = branch
        OR (e1.branch = default_branch AND e1.from < branched_from)
    )
    AND e1.to IS NULL
    AND (
        e2.branch = branch
        OR (e2.branch = default_branch AND e2.from < branched_from)
    )
    AND e2.to IS NULL
    WITH attr, av, e1.status = "active" AND e2.status = "active" AS is_active
    ORDER BY e2.branch_level DESC, e2.from DESC, e2.status ASC, e1.branch_level DESC, e1.from DESC, e1.status ASC
    LIMIT 1
    WITH attr, av
    WHERE is_active = TRUE
    RETURN CASE
        WHEN attr.name = $prefix_attribute_name THEN av.value
        ELSE NULL
    END AS prefix_value,
    CASE
        WHEN attr.name = $address_attribute_name THEN av.value
        ELSE NULL
    END AS address_value
}
RETURN branch, namespace_uuid, ip_node.uuid AS node_uuid, prefix_value, address_value
        """ % {
            "prefix_kind": InfrahubKind.IPPREFIX,
            "address_kind": InfrahubKind.IPADDRESS,
            "namespace_kind": InfrahubKind.IPNAMESPACE,
        }
        self.add_to_query(query)
        self.return_labels = ["branch", "namespace_uuid", "node_uuid", "prefix_value", "address_value"]

    def get_nodes_to_reconcile(self) -> list[IpNodeDetails]:
        ip_node_details = []
        for result in self.get_results():
            prefix_value = result.get_as_str("prefix_value")
            address_value = result.get_as_str("address_value")
            if prefix_value:
                ip_value: AllIPTypes = ipaddress.ip_network(address=prefix_value)
            elif address_value:
                ip_value = ipaddress.ip_interface(address=address_value)
            else:
                continue
            ip_node_details.append(
                IpNodeDetails(
                    branch=result.get_as_type("branch", str),
                    ip_value=ip_value,
                    namespace=result.get_as_type("namespace_uuid", str),
                    node_uuid=result.get_as_type("node_uuid", str),
                )
            )
        return ip_node_details


class DeleteSelfParentRelationshipsQuery(Query):
    name = "delete_self_parent_relationships"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, uuids_to_check: list[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.uuids_to_check = uuids_to_check

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["uuids_to_check"] = self.uuids_to_check
        query = """
MATCH (n:Node)-[e1:IS_RELATED]->(:Relationship {name: "parent__child"})-[e2:IS_RELATED {branch: e1.branch, status: e1.status, from: e1.from}]->(n)
WHERE n.uuid IN $uuids_to_check
DELETE e1, e2
        """
        self.add_to_query(query)


class Migration039(ArbitraryMigration):
    """
    Identify all IP prefixes/addresses that have been updated on a branch and reconcile them on that branch
    If any of the identified IP prefixes/addresses are their own parent/child, delete those illegal edges before reconciling.
    """

    name: str = "039_ipam_reconcile_updated"
    minimum_version: int = 38

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._reconcilers_by_branch: dict[str, IpamReconciler] = {}

    async def _get_reconciler(self, db: InfrahubDatabase, branch_name: str) -> IpamReconciler:
        if branch_name not in self._reconcilers_by_branch:
            branch = await Branch.get_by_name(db=db, name=branch_name)
            self._reconcilers_by_branch[branch_name] = IpamReconciler(db=db, branch=branch)
        return self._reconcilers_by_branch[branch_name]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        console = Console()
        result = MigrationResult()
        # load schemas from database into registry
        initialize_lock()
        await initialization(db=db)

        console.print("Identifying IP prefixes/addresses to reconcile...", end="")
        find_nodes_query = await FindNodesToReconcileQuery.init(db=db)
        await find_nodes_query.execute(db=db)
        console.print("done")

        # we need to delete the self-parent relationships before reconciling b/c the
        # reconciler cannot correctly handle a prefix that is its own parent
        ip_node_details_list = find_nodes_query.get_nodes_to_reconcile()
        uuids_to_check = {ip_node_details.node_uuid for ip_node_details in ip_node_details_list}
        console.print(f"{len(ip_node_details_list)} IP prefixes/addresses will be reconciled")

        console.print("Deleting any self-parent relationships...", end="")
        delete_self_parent_relationships_query = await DeleteSelfParentRelationshipsQuery.init(
            db=db, uuids_to_check=list(uuids_to_check)
        )
        await delete_self_parent_relationships_query.execute(db=db)
        console.print("done")

        with Progress() as progress:
            reconcile_task = progress.add_task("Reconciling IP prefixes/addresses...", total=len(ip_node_details_list))

            for ip_node_details in ip_node_details_list:
                reconciler = await self._get_reconciler(db=db, branch_name=ip_node_details.branch)
                await reconciler.reconcile(
                    ip_value=ip_node_details.ip_value,
                    namespace=ip_node_details.namespace,
                    node_uuid=ip_node_details.node_uuid,
                )
                progress.update(reconcile_task, advance=1)

        return result
