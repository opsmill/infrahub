from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.progress import Progress

from infrahub.core.branch.models import Branch
from infrahub.core.initialization import get_root_node
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.shared import MigrationResult, get_migration_console
from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp
from infrahub.log import get_logger
from infrahub.profiles.node_applier import NodeProfilesApplier

from ..shared import MigrationRequiringRebase
from .load_schema_branch import get_or_load_schema_branch

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()


class GetUpdatedProfilesForBranchQuery(Query):
    """
    Get CoreProfile UUIDs with updated attributes on this branch
    """

    name = "get_profiles_by_branch"
    type = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["branch"] = self.branch.name
        query = """
MATCH (profile:CoreProfile)-[:HAS_ATTRIBUTE]->(attr:Attribute)-[e:HAS_VALUE]->(:AttributeValue)
WHERE e.branch = $branch
WITH DISTINCT profile.uuid AS profile_uuid
        """
        self.add_to_query(query)
        self.return_labels = ["profile_uuid"]

    def get_profile_ids(self) -> list[str]:
        """Get list of updated profile UUIDs"""
        return [result.get_as_type("profile_uuid", str) for result in self.get_results()]


class GetNodesWithProfileUpdatesForBranchQuery(Query):
    """
    Get Node UUIDs by which branches they have updated profiles on
    """

    name = "get_nodes_with_profile_updates_by_branch"
    type = QueryType.READ

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["branch"] = self.branch.name
        query = """
MATCH (node:Node)-[e:IS_RELATED]->(:Relationship {name: "node__profile"})
WHERE NOT node:CoreProfile
AND e.branch = $branch
WITH DISTINCT node.uuid AS node_uuid
        """
        self.add_to_query(query)
        self.return_labels = ["node_uuid"]

    def get_node_ids(self) -> list[str]:
        """Get list of updated node UUIDs"""
        return [result.get_as_type("node_uuid", str) for result in self.get_results()]


class Migration042(MigrationRequiringRebase):
    """
    Save profile attribute values on each node using the profile in the database
    For any profile that has updates on a given branch (including default branch)
    - run NodeProfilesApplier.apply_profiles on each node related to the profile on that branch
    For any node that has an updated relationship to a profile on a given branch
    - run NodeProfilesApplier.apply_profiles on the node on that branch
    """

    name: str = "042_profile_attrs_in_db"
    minimum_version: int = 41

    def _get_profile_applier(self, db: InfrahubDatabase, branch: Branch) -> NodeProfilesApplier:
        return NodeProfilesApplier(db=db, branch=branch)

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        root_node = await get_root_node(db=db, initialize=False)
        default_branch_name = root_node.default_branch
        default_branch = await Branch.get_by_name(db=db, name=default_branch_name)
        return await self._do_execute_for_branch(db=db, branch=default_branch)

    async def execute_against_branch(self, db: InfrahubDatabase, branch: Branch) -> MigrationResult:
        return await self._do_execute_for_branch(db=db, branch=branch)

    async def _do_execute_for_branch(self, db: InfrahubDatabase, branch: Branch) -> MigrationResult:
        console = get_migration_console()
        result = MigrationResult()
        await get_or_load_schema_branch(db=db, branch=branch)

        console.print(f"Gathering profiles for branch {branch.name}...", end="")
        get_updated_profiles_for_branch_query = await GetUpdatedProfilesForBranchQuery.init(db=db, branch=branch)
        await get_updated_profiles_for_branch_query.execute(db=db)
        profile_ids = get_updated_profiles_for_branch_query.get_profile_ids()

        profiles_map = await NodeManager.get_many(db=db, branch=branch, ids=list(profile_ids))
        console.print("done")

        node_ids_to_update: set[str] = set()
        with Progress(console=console) as progress:
            gather_nodes_task = progress.add_task(
                f"Gathering affected objects for each profile on branch {branch.name}...", total=len(profiles_map)
            )

            for profile in profiles_map.values():
                node_relationship_manager = profile.get_relationship("related_nodes")
                node_peers = await node_relationship_manager.get_db_peers(db=db)
                node_ids_to_update.update(str(peer.peer_id) for peer in node_peers)
                progress.update(gather_nodes_task, advance=1)
        console.log(f"Collected nodes impacted by profiles on branch {branch.name}.")

        console.print("Identifying nodes with profile updates by branch...", end="")
        get_nodes_with_profile_updates_by_branch_query = await GetNodesWithProfileUpdatesForBranchQuery.init(
            db=db, branch=branch
        )
        await get_nodes_with_profile_updates_by_branch_query.execute(db=db)
        node_ids_to_update.update(get_nodes_with_profile_updates_by_branch_query.get_node_ids())
        console.print("done")

        right_now = Timestamp()
        console.log("Applying profiles to nodes...")
        with Progress(console=console) as progress:
            apply_task = progress.add_task("Applying profiles to nodes...", total=len(node_ids_to_update))
            applier = self._get_profile_applier(db=db, branch=branch)
            for node_id in node_ids_to_update:
                node = await NodeManager.get_one(db=db, branch=branch, id=node_id, at=right_now)
                if node:
                    updated_field_names = await applier.apply_profiles(node=node)
                    if updated_field_names:
                        await node.save(db=db, fields=updated_field_names, at=right_now)
                progress.update(apply_task, advance=1)
        console.log("Completed applying profiles to nodes.")

        return result
