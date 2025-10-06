from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.progress import Progress

from infrahub.core.branch.models import Branch
from infrahub.core.initialization import initialization
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.lock import initialize_lock
from infrahub.log import get_logger
from infrahub.profiles.node_applier import NodeProfilesApplier

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase

log = get_logger()


class GetProfilesByBranchQuery(Query):
    """
    Get CoreProfile UUIDs by which branches they have attribute updates on
    """

    name = "get_profiles_by_branch"
    type = QueryType.READ
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (profile:CoreProfile)-[:HAS_ATTRIBUTE]->(attr:Attribute)-[e:HAS_VALUE]->(:AttributeValue)
WITH DISTINCT profile.uuid AS profile_uuid, e.branch AS branch
RETURN profile_uuid, collect(branch) AS branches
        """
        self.add_to_query(query)
        self.return_labels = ["profile_uuid", "branches"]

    def get_profile_ids_by_branch(self) -> dict[str, set[str]]:
        """Get dictionary of branch names to set of updated profile UUIDs"""
        profiles_by_branch = defaultdict(set)
        for result in self.get_results():
            profile_uuid = result.get_as_type("profile_uuid", str)
            branches = result.get_as_type("branches", list[str])
            for branch in branches:
                profiles_by_branch[branch].add(profile_uuid)
        return profiles_by_branch


class GetNodesWithProfileUpdatesByBranchQuery(Query):
    """
    Get Node UUIDs by which branches they have updated profiles on
    """

    name = "get_nodes_with_profile_updates_by_branch"
    type = QueryType.READ
    insert_return = False

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        query = """
MATCH (node:Node)-[e1:IS_RELATED]->(:Relationship {name: "node__profile"})
WHERE NOT node:CoreProfile
WITH DISTINCT node.uuid AS node_uuid, e1.branch AS branch
RETURN node_uuid, collect(branch) AS branches
        """
        self.add_to_query(query)
        self.return_labels = ["node_uuid", "branches"]

    def get_node_ids_by_branch(self) -> dict[str, set[str]]:
        """Get dictionary of branch names to set of updated node UUIDs"""
        nodes_by_branch = defaultdict(set)
        for result in self.get_results():
            node_uuid = result.get_as_type("node_uuid", str)
            branches = result.get_as_type("branches", list[str])
            for branch in branches:
                nodes_by_branch[branch].add(node_uuid)
        return nodes_by_branch


class Migration040(ArbitraryMigration):
    """
    Save profile attribute values on each node using the profile in the database
    For any profile that has updates on a given branch (including default branch)
    - run NodeProfilesApplier.apply_profiles on each node related to the profile on that branch
    For any node that has an updated relationship to a profile on a given branch
    - run NodeProfilesApplier.apply_profiles on the node on that branch
    """

    name: str = "040_profile_attrs_in_db"
    minimum_version: int = 39

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._appliers_by_branch: dict[str, NodeProfilesApplier] = {}

    async def _get_profile_applier(self, db: InfrahubDatabase, branch_name: str) -> NodeProfilesApplier:
        if branch_name not in self._appliers_by_branch:
            branch = await Branch.get_by_name(db=db, name=branch_name)
            self._appliers_by_branch[branch_name] = NodeProfilesApplier(db=db, branch=branch)
        return self._appliers_by_branch[branch_name]

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        console = Console()
        result = MigrationResult()
        # load schemas from database into registry
        initialize_lock()
        await initialization(db=db)

        console.print("Gathering profiles for each branch...", end="")
        get_profiles_by_branch_query = await GetProfilesByBranchQuery.init(db=db)
        await get_profiles_by_branch_query.execute(db=db)
        profiles_ids_by_branch = get_profiles_by_branch_query.get_profile_ids_by_branch()

        profiles_by_branch: dict[str, list[Node]] = {}
        for branch_name, profile_ids in profiles_ids_by_branch.items():
            profiles_map = await NodeManager.get_many(db=db, branch=branch_name, ids=list(profile_ids))
            profiles_by_branch[branch_name] = list(profiles_map.values())
        console.print("done")

        node_ids_to_update_by_branch: dict[str, set[str]] = defaultdict(set)
        total_size = sum(len(profiles) for profiles in profiles_by_branch.values())
        with Progress() as progress:
            gather_nodes_task = progress.add_task(
                "Gathering affected objects for each profile on each branch...", total=total_size
            )

            for branch_name, profiles in profiles_by_branch.items():
                for profile in profiles:
                    node_relationship_manager = profile.get_relationship("related_nodes")
                    node_peers = await node_relationship_manager.get_db_peers(db=db)
                    node_ids_to_update_by_branch[branch_name].update({str(peer.peer_id) for peer in node_peers})
                    progress.update(gather_nodes_task, advance=1)

        console.print("Identifying nodes with profile updates by branch...", end="")
        get_nodes_with_profile_updates_by_branch_query = await GetNodesWithProfileUpdatesByBranchQuery.init(db=db)
        await get_nodes_with_profile_updates_by_branch_query.execute(db=db)
        nodes_ids_by_branch = get_nodes_with_profile_updates_by_branch_query.get_node_ids_by_branch()
        for branch_name, node_ids in nodes_ids_by_branch.items():
            node_ids_to_update_by_branch[branch_name].update(node_ids)
        console.print("done")

        right_now = Timestamp()
        total_size = sum(len(node_ids) for node_ids in node_ids_to_update_by_branch.values())
        with Progress() as progress:
            apply_task = progress.add_task("Applying profiles to nodes...", total=total_size)
            for branch_name, node_ids in node_ids_to_update_by_branch.items():
                applier = await self._get_profile_applier(db=db, branch_name=branch_name)
                for node_id in node_ids:
                    node = await NodeManager.get_one(db=db, branch=branch_name, id=node_id, at=right_now)
                    if node:
                        updated_field_names = await applier.apply_profiles(node=node)
                        if updated_field_names:
                            await node.save(db=db, fields=updated_field_names, at=right_now)
                    progress.update(apply_task, advance=1)

        return result
