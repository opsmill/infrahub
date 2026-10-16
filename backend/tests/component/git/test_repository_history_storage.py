"""Adding a repository adds the same number of vertices and edges whatever the length of its commit history, and adds no entry to the branch diff."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, InfrahubKind
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.utils import count_nodes, count_relationships
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.git import LocalRemote
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

SHORT_HISTORY = 2
LONG_HISTORY = 300

REPOSITORY_COMMIT = """
query RepositoryCommit($id: ID!) {
    CoreRepository(ids: [$id]) {
        edges { node { commit { value } } }
    }
}
"""


class GraphSize(NamedTuple):
    vertices: int
    edges: int


class AddedRepository(NamedTuple):
    growth: GraphSize
    tag_id: str


def create_remote(directory: Path, commits: int) -> LocalRemote:
    """Create a remote whose trunk holds ``commits`` commits, at least two, and ends at the same files as every other remote.

    Each commit message names the remote, so two remotes created within the same second never share a head commit.
    """
    remote = LocalRemote.create(directory=directory, trunk="main", branches=[])
    data_file = directory / "data.txt"
    for index in range(2, commits + 1):
        data_file.write_text("final\n" if index == commits else f"v{index}\n", encoding="utf-8")
        remote.repo.index.add(["data.txt"])
        remote.repo.index.commit(f"Commit {index} of {directory.name}")
    assert int(remote.repo.git.rev_list("--count", "main")) == commits
    return remote


async def measure_graph(db: InfrahubDatabase) -> GraphSize:
    return GraphSize(vertices=await count_nodes(db=db), edges=await count_relationships(db=db))


async def add_repository_on_its_own_branch(
    db: InfrahubDatabase, client: InfrahubClient, tmp_path: Path, name: str, commits: int
) -> AddedRepository:
    """Add a repository with ``commits`` commits on a new branch, and a tag on the same branch.

    The repository node is branch-agnostic, so the tag is the one entry the branch diff is expected to
    hold, and a diff that was never computed cannot pass as an empty one.
    """
    remote = create_remote(directory=tmp_path / name, commits=commits)
    await client.branch.create(branch_name=name)
    tag = await client.create(kind=InfrahubKind.TAG, data={"name": f"{name}-tag"}, branch=name)
    await tag.save()

    before = await measure_graph(db=db)
    repository = await client.create(
        kind=InfrahubKind.REPOSITORY, data={"name": name, "location": str(remote.directory)}, branch=name
    )
    await repository.save()

    imported = await client.execute_graphql(query=REPOSITORY_COMMIT, variables={"id": repository.id}, branch_name=name)
    assert imported["CoreRepository"]["edges"] == [{"node": {"commit": {"value": remote.repo.commit("main").hexsha}}}]
    after = await measure_graph(db=db)
    return AddedRepository(
        growth=GraphSize(vertices=after.vertices - before.vertices, edges=after.edges - before.edges), tag_id=tag.id
    )


async def compute_branch_diff(db: InfrahubDatabase, default_branch: Branch, branch_name: str) -> EnrichedDiffRoot:
    branch = await Branch.get_by_name(name=branch_name, db=db)
    component_registry = get_component_registry()
    coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    metadata = await coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    return await diff_repository.get_one(diff_branch_name=metadata.diff_branch_name, diff_id=metadata.uuid)


class TestRepositoryHistoryStorage(TestInfrahubApp):
    async def test_adding_a_repository_stores_nothing_per_commit_and_adds_nothing_to_the_branch_diff(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        initialize_registry: None,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
        git_repos_dir: Path,
        tmp_path: Path,
    ) -> None:
        # Attribute values are shared vertices, so the first repository creates some that every later one reuses.
        await add_repository_on_its_own_branch(
            db=db, client=client, tmp_path=tmp_path, name="first-repository", commits=SHORT_HISTORY
        )

        short = await add_repository_on_its_own_branch(
            db=db, client=client, tmp_path=tmp_path, name="short-history", commits=SHORT_HISTORY
        )
        long = await add_repository_on_its_own_branch(
            db=db, client=client, tmp_path=tmp_path, name="long-history", commits=LONG_HISTORY
        )

        assert short.growth.vertices > 0
        assert short.growth.edges > 0
        assert long.growth == short.growth

        for branch_name, added in (("short-history", short), ("long-history", long)):
            diff = await compute_branch_diff(db=db, default_branch=default_branch, branch_name=branch_name)
            assert [(node.identifier.uuid, node.identifier.kind, node.action) for node in diff.nodes] == [
                (added.tag_id, InfrahubKind.TAG, DiffAction.ADDED)
            ]
