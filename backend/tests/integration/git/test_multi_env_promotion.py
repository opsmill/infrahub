"""Multi-environment single-repo validation: read-only promotion semantics.

A read-only repository pinned to a ref is the consumer side of the multi-environment pattern:
promotion happens by re-importing the ref or by bumping the ref to a new tag / commit. The canonical
workflow never acts on the primary branch directly: create an Infrahub branch, bump the ref there,
let the import load into the branch, review, and merge — normally through a proposed change. These
tests pin the promotion contract — tag bumps, moved tags, commit-SHA refs, the branch-staged
workflow — and what content a promotion carries (object and schema removals stay, by design).

Uses local bare remotes (no external git server needed) plus the in-process app.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from git import Repo

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.git.models import GitReadOnlyRepositoryImportCommit, GitRepositoryMerge
from infrahub.git.tasks import import_read_only_repository_last_commit, merge_git_repository
from infrahub.proposed_change.constants import ProposedChangeState
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.protocols import CoreReadOnlyRepository
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

SOURCE_BRANCH = "develop"


def _object_file(tag_name: str) -> str:
    return f"""---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: BuiltinTag
  data:
    - name: {tag_name}
"""


SCHEMA_FILE = """---
version: "1.0"
nodes:
  - name: Widget
    namespace: Testing
    label: Widget
    attributes:
      - name: name
        kind: Text
        unique: true
"""

CONFIG_WITH_OBJECTS = """---
objects:
  - objects/tags.yml
"""

CONFIG_WITH_SCHEMA = """---
schemas:
  - schemas/widget.yml
"""


class _SeededRemote:
    """A local bare remote plus its seeding clone, for staging commits and tags."""

    def __init__(self, base_dir: Path) -> None:
        self.bare_path = base_dir / "remote.git"
        Repo.init(self.bare_path, bare=True, initial_branch="main")

        self.seed_path = base_dir / "seed"
        self.seed = Repo.init(self.seed_path, initial_branch="main")
        with self.seed.config_writer() as cfg:
            cfg.set_value("user", "name", "Infrahub Test")
            cfg.set_value("user", "email", "infrahub@test.local")
        (self.seed_path / ".infrahub.yml").write_text("---\n")
        self.seed.index.add([".infrahub.yml"])
        self.seed.index.commit("Initial commit")
        self.seed.create_head(SOURCE_BRANCH)
        self.seed.create_remote("origin", str(self.bare_path))
        self.seed.remotes.origin.push(refspec=["main", SOURCE_BRANCH])

    def commit_files(self, files: dict[str, str], message: str) -> str:
        """Commit ``files`` (path -> content) on the source branch and push; return the SHA."""
        self.seed.git.checkout(SOURCE_BRANCH)
        for rel_path, content in files.items():
            target = self.seed_path / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            self.seed.index.add([rel_path])
        sha = str(self.seed.index.commit(message))
        self.seed.remotes.origin.push(refspec=[SOURCE_BRANCH])
        return sha

    def remove_files(self, paths: list[str], message: str) -> str:
        """Remove ``paths`` on the source branch and push; return the SHA."""
        self.seed.git.checkout(SOURCE_BRANCH)
        self.seed.index.remove(paths, working_tree=True)
        sha = str(self.seed.index.commit(message))
        self.seed.remotes.origin.push(refspec=[SOURCE_BRANCH])
        return sha

    def tag(self, name: str, sha: str, force: bool = False, annotated: bool = False) -> None:
        """Create (or force-move) a tag at ``sha`` and push it; annotated tags carry a tag object."""
        message = f"release {name}" if annotated else None
        self.seed.create_tag(name, ref=sha, force=force, message=message)
        self.seed.remotes.origin.push(refspec=[f"refs/tags/{name}"], force=force)

    def rewrite_branch_history(self) -> str:
        """Rewrite the source branch onto an unrelated history and force-push; return the new tip."""
        self.seed.git.checkout(SOURCE_BRANCH)
        self.seed.git.reset("--hard", "main")
        (self.seed_path / "rewritten.txt").write_text("rewritten history\n")
        self.seed.index.add(["rewritten.txt"])
        sha = str(self.seed.index.commit("Rewrite branch history"))
        self.seed.remotes.origin.push(refspec=[SOURCE_BRANCH], force=True)
        return sha

    def branch_tip(self) -> str:
        return str(Repo(self.bare_path).commit(SOURCE_BRANCH))


async def _register_readonly(client: InfrahubClient, repo_name: str, location: str, ref: str) -> str:
    """Register a read-only repository pinned (at creation) to ``ref``; return the node id."""
    node = await client.create(
        kind=InfrahubKind.READONLYREPOSITORY,
        data={"name": repo_name, "location": location, "ref": ref},
    )
    await node.save()
    return node.id


async def _import_ref(node_id: str, repo_name: str, ref: str) -> None:
    """Run the read-only import flow for ``ref`` — the reimport promotion mechanism."""
    await import_read_only_repository_last_commit(
        model=GitReadOnlyRepositoryImportCommit(
            repository_id=node_id,
            repository_name=repo_name,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            infrahub_branch_name="main",
            ref=ref,
        )
    )


async def _bump_ref(client: InfrahubClient, node_id: str, repo_name: str, new_ref: str) -> None:
    """Bump the repository's tracked ref and import it — the ref-bump promotion mechanism.

    The node's ref attribute must change first: recording the imported commit re-enters the update
    path, which re-imports using the ref stored on the node — a bump passed only to the import flow
    would be clobbered by that re-import of the old ref.
    """
    node = await client.get(kind=InfrahubKind.READONLYREPOSITORY, id=node_id)
    node.ref.value = new_ref
    await node.save()
    await _import_ref(node_id, repo_name, new_ref)


async def _recorded_commit(db: InfrahubDatabase, node_id: str) -> str:
    repo: CoreReadOnlyRepository = await NodeManager.get_one(
        db=db, id=node_id, kind=InfrahubKind.READONLYREPOSITORY, raise_on_error=True
    )
    commit = repo.commit.value
    assert commit is not None
    return commit


class TestMultiEnvPromotion(TestInfrahubApp):
    """Promotion contract of a read-only consumer pinned to a ref on a shared remote."""

    async def test_new_tag_ref_bump_promotes(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
    ) -> None:
        """Bumping the ref to a newly created tag advances the consumer to that tag's commit.

        This is the release-flow promotion mechanism: pin the consumer to a tag, cut a new tag for
        the next release, bump the ref. The forward bump targets an annotated tag (a tag object that
        must be peeled to its commit), and the rollback bump returns to the previous lightweight tag
        — both directions must land exactly on the tag's commit.
        """
        remote = _SeededRemote(tmp_path)
        v1_sha = remote.branch_tip()
        remote.tag("v1", v1_sha)

        node_id = await _register_readonly(client, "promo-tag-bump-repo", str(remote.bare_path), "v1")
        await _import_ref(node_id, "promo-tag-bump-repo", "v1")
        assert await _recorded_commit(db, node_id) == v1_sha

        v2_sha = remote.commit_files({"release.txt": "v2 content\n"}, "Release v2")
        remote.tag("v2", v2_sha, annotated=True)

        await _bump_ref(client, node_id, "promo-tag-bump-repo", "v2")
        assert await _recorded_commit(db, node_id) == v2_sha

        # Rollback: bump the ref back to the previous release.
        await _bump_ref(client, node_id, "promo-tag-bump-repo", "v1")
        assert await _recorded_commit(db, node_id) == v1_sha

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "a force-moved tag is not refreshed on reimport: the fetch refuses to clobber the "
            "existing local tag, so the consumer silently stays on the tag's old commit"
        ),
    )
    async def test_reimport_follows_moved_tag(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
    ) -> None:
        """Re-cutting an existing tag (force-move) and reimporting must advance the consumer.

        Re-tagging a release (``git tag -f`` + force push) is a common, if discouraged, release
        practice. The consumer's reimport must either follow the moved tag or fail loudly — silently
        staying on the old commit while the operator believes the promotion happened is the failure
        mode.
        """
        remote = _SeededRemote(tmp_path)
        old_sha = remote.branch_tip()
        remote.tag("v1", old_sha)

        node_id = await _register_readonly(client, "promo-moved-tag-repo", str(remote.bare_path), "v1")
        await _import_ref(node_id, "promo-moved-tag-repo", "v1")
        assert await _recorded_commit(db, node_id) == old_sha

        new_sha = remote.commit_files({"hotfix.txt": "hotfix content\n"}, "Hotfix onto v1")
        remote.tag("v1", new_sha, force=True)

        await _import_ref(node_id, "promo-moved-tag-repo", "v1")
        # Intended contract: the consumer follows the moved tag (or the import fails loudly).
        assert await _recorded_commit(db, node_id) == new_sha

    async def test_ref_commit_sha_pins_and_bumps(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
    ) -> None:
        """A commit SHA is a valid ref to pin to, and bumping to another SHA promotes.

        The strictest pinning mode: the consumer tracks an exact commit rather than a movable name.
        """
        remote = _SeededRemote(tmp_path)
        sha1 = remote.branch_tip()

        node_id = await _register_readonly(client, "promo-sha-repo", str(remote.bare_path), sha1)
        await _import_ref(node_id, "promo-sha-repo", sha1)
        assert await _recorded_commit(db, node_id) == sha1

        sha2 = remote.commit_files({"advance.txt": "next pinned state\n"}, "Advance for SHA bump")

        await _bump_ref(client, node_id, "promo-sha-repo", sha2)
        assert await _recorded_commit(db, node_id) == sha2

    async def test_rollback_reverts_objects_but_not_schema(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
    ) -> None:
        """Rolling back to an older tag reverts file-defined objects but never the schema.

        Import is an apply, not a declarative convergence: rolling the ref back re-runs the import
        with the older files. Objects reconcile (the newer release's additions are garbage-collected,
        modified values revert to the older file's), but schema loads are additive-only — a node type
        introduced by the newer release stays loaded after the rollback. Rollback restores the pin
        and the file-defined content, not the full instance state — and restored objects come back
        as new nodes (identity churn), so references to the originals dangle.
        """
        remote = _SeededRemote(tmp_path)
        v1_sha = remote.commit_files(
            {".infrahub.yml": CONFIG_WITH_OBJECTS, "objects/tags.yml": _object_file("rollback-v1-tag")},
            "Release v1 content",
        )
        remote.tag("v1", v1_sha)

        repo_name = "promo-rollback-repo"
        node_id = await _register_readonly(client, repo_name, str(remote.bare_path), "v1")
        await _import_ref(node_id, repo_name, "v1")
        v1_tags = await client.filters(kind="BuiltinTag", name__value="rollback-v1-tag")
        assert len(v1_tags) == 1
        v1_tag_id_before = v1_tags[0].id

        # v2 adds a schema node type, adds an object, and replaces the v1 object.
        v2_sha = remote.commit_files(
            {
                ".infrahub.yml": "---\nobjects:\n  - objects/tags.yml\nschemas:\n  - schemas/widget.yml\n",
                "objects/tags.yml": _object_file("rollback-v2-tag"),
                "schemas/widget.yml": SCHEMA_FILE,
            },
            "Release v2 content",
        )
        remote.tag("v2", v2_sha)
        await _bump_ref(client, node_id, repo_name, "v2")
        assert await _recorded_commit(db, node_id) == v2_sha
        assert len(await client.filters(kind="BuiltinTag", name__value="rollback-v2-tag")) == 1
        widget = await client.schema.get(kind="TestingWidget", refresh=True)
        assert widget.kind == "TestingWidget"

        # Roll back to v1.
        await _bump_ref(client, node_id, repo_name, "v1")
        assert await _recorded_commit(db, node_id) == v1_sha

        # File-defined objects reconcile back to the v1 set.
        v1_tags_after = await client.filters(kind="BuiltinTag", name__value="rollback-v1-tag")
        assert len(v1_tags_after) == 1
        assert len(await client.filters(kind="BuiltinTag", name__value="rollback-v2-tag")) == 0

        # Identity churn: the restored object is a NEW node, not the original — it was deleted by the
        # newer release's reconciliation and recreated by the rollback import. Anything that
        # referenced the original id (user relationships, external systems) is now dangling.
        assert v1_tags_after[0].id != v1_tag_id_before

        # The schema introduced by v2 persists — rollback does not unload schema.
        widget_after = await client.schema.get(kind="TestingWidget", refresh=True)
        assert widget_after.kind == "TestingWidget"

    async def test_object_replacement_garbage_collects_on_ref_bump(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
    ) -> None:
        """An object replaced within a still-present object file is garbage-collected on promotion.

        Repository-sourced objects are group-tracked: when the object import runs and a previously
        tracked object is no longer produced, it is deleted. This guards the reconciliation that a
        promotion carrying content changes relies on.
        """
        remote = _SeededRemote(tmp_path)
        v1_sha = remote.commit_files(
            {".infrahub.yml": CONFIG_WITH_OBJECTS, "objects/tags.yml": _object_file("replaced-tag")},
            "Add tag object",
        )
        remote.tag("v1", v1_sha)

        node_id = await _register_readonly(client, "promo-object-swap-repo", str(remote.bare_path), "v1")
        await _import_ref(node_id, "promo-object-swap-repo", "v1")
        assert len(await client.filters(kind="BuiltinTag", name__value="replaced-tag")) == 1

        v2_sha = remote.commit_files({"objects/tags.yml": _object_file("replacement-tag")}, "Swap tag object")
        remote.tag("v2", v2_sha)
        await _bump_ref(client, node_id, "promo-object-swap-repo", "v2")

        assert len(await client.filters(kind="BuiltinTag", name__value="replacement-tag")) == 1
        # The previously tracked object was reconciled away by the import that ran.
        assert len(await client.filters(kind="BuiltinTag", name__value="replaced-tag")) == 0

    async def test_object_removal_not_propagated(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
    ) -> None:
        """Objects from a removed object file persist on the consumer after promotion.

        Documented-limitation guard: group-tracked garbage collection reconciles only within an
        import run that happens. A promotion that removes the object file and its config entry skips
        the object import entirely, so the objects the file created remain on every environment that
        imported them. Retiring repository-sourced objects therefore requires either keeping the file
        listed with the objects removed from it, or manual cleanup.
        """
        remote = _SeededRemote(tmp_path)
        v1_sha = remote.commit_files(
            {".infrahub.yml": CONFIG_WITH_OBJECTS, "objects/tags.yml": _object_file("gc-tag")}, "Add tag object"
        )
        remote.tag("v1", v1_sha)

        node_id = await _register_readonly(client, "promo-object-gc-repo", str(remote.bare_path), "v1")
        await _import_ref(node_id, "promo-object-gc-repo", "v1")

        tags = await client.filters(kind="BuiltinTag", name__value="gc-tag")
        assert len(tags) == 1

        remote.commit_files({".infrahub.yml": "---\n"}, "Drop objects from config")
        v2_sha = remote.remove_files(["objects/tags.yml"], "Remove tag object file")
        remote.tag("v2", v2_sha)

        await _bump_ref(client, node_id, "promo-object-gc-repo", "v2")

        # Current contract: the object persists after its file's removal is promoted.
        tags_after = await client.filters(kind="BuiltinTag", name__value="gc-tag")
        assert len(tags_after) == 1

    async def test_schema_removal_not_propagated(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
    ) -> None:
        """A schema removed from the repo persists on the consumer — schema imports are additive.

        Documented-limitation guard: promoting a schema *removal* through environments does nothing;
        the node type stays loaded on every instance that ever imported it. Operators must plan
        schema retirement out of band.
        """
        remote = _SeededRemote(tmp_path)
        v1_sha = remote.commit_files(
            {".infrahub.yml": CONFIG_WITH_SCHEMA, "schemas/widget.yml": SCHEMA_FILE}, "Add widget schema"
        )
        remote.tag("v1", v1_sha)

        node_id = await _register_readonly(client, "promo-schema-repo", str(remote.bare_path), "v1")
        await _import_ref(node_id, "promo-schema-repo", "v1")

        widget = await client.schema.get(kind="TestingWidget", refresh=True)
        assert widget.kind == "TestingWidget"

        remote.commit_files({".infrahub.yml": "---\n"}, "Drop schema from config")
        v2_sha = remote.remove_files(["schemas/widget.yml"], "Remove widget schema file")
        remote.tag("v2", v2_sha)

        await _bump_ref(client, node_id, "promo-schema-repo", "v2")

        # Current contract: the schema persists after the removal is promoted.
        widget_after = await client.schema.get(kind="TestingWidget", refresh=True)
        assert widget_after.kind == "TestingWidget"

    async def test_ref_bump_inside_branch_promotes_after_merge(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
    ) -> None:
        """Bumping the ref inside an Infrahub branch stays isolated, then promotes on merge.

        A release flow may stage the ref bump in a branch (review the promotion before applying).
        The bump must import into the branch only — the primary branch keeps the old commit — and
        merging the branch must carry both the recorded ref/commit and the imported content onto the
        primary branch.
        """
        remote = _SeededRemote(tmp_path)
        v1_sha = remote.branch_tip()
        remote.tag("v1", v1_sha)

        repo_name = "promo-branch-bump-repo"
        node_id = await _register_readonly(client, repo_name, str(remote.bare_path), "v1")
        await _import_ref(node_id, repo_name, "v1")
        assert await _recorded_commit(db, node_id) == v1_sha

        v2_sha = remote.commit_files(
            {".infrahub.yml": CONFIG_WITH_OBJECTS, "objects/tags.yml": _object_file("branch-promoted-tag")},
            "Release v2 with objects",
        )
        remote.tag("v2", v2_sha)

        branch = await client.branch.create(branch_name="promo-ref-bump")

        # The ref bump staged in the branch: update the node's ref there and run the import for it.
        repo_in_branch = await client.get(kind=InfrahubKind.READONLYREPOSITORY, id=node_id, branch=branch.name)
        repo_in_branch.ref.value = "v2"
        await repo_in_branch.save()
        await import_read_only_repository_last_commit(
            model=GitReadOnlyRepositoryImportCommit(
                repository_id=node_id,
                repository_name=repo_name,
                repository_kind=InfrahubKind.READONLYREPOSITORY,
                infrahub_branch_name=branch.name,
                ref="v2",
            )
        )

        # Isolation before the merge: the branch advanced, the primary branch did not.
        repo_branch: CoreReadOnlyRepository = await NodeManager.get_one(
            db=db, id=node_id, kind=InfrahubKind.READONLYREPOSITORY, branch=branch.name, raise_on_error=True
        )
        assert repo_branch.commit.value == v2_sha
        assert await _recorded_commit(db, node_id) == v1_sha

        await client.branch.merge(branch_name=branch.name)

        # Promotion after the merge: the primary branch carries the new commit and the content.
        assert await _recorded_commit(db, node_id) == v2_sha
        tags = await client.filters(kind="BuiltinTag", name__value="branch-promoted-tag")
        assert len(tags) == 1

    async def test_promotion_via_branch_and_proposed_change(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
        prefect_test_fixture: None,
        bus_simulator: BusSimulator,
    ) -> None:
        """The canonical promotion: ref bump staged in a branch, reviewed and merged via a proposed change.

        Nothing acts on the primary branch directly. The ref bump imports into an Infrahub branch,
        the branch is put up as a proposed change (running the validation pipeline), and merging the
        proposed change carries the recorded ref/commit and the imported content onto the primary
        branch.
        """
        remote = _SeededRemote(tmp_path)
        v1_sha = remote.branch_tip()
        remote.tag("v1", v1_sha)

        repo_name = "promo-pc-repo"
        node_id = await _register_readonly(client, repo_name, str(remote.bare_path), "v1")
        await _import_ref(node_id, repo_name, "v1")
        assert await _recorded_commit(db, node_id) == v1_sha

        v2_sha = remote.commit_files(
            {".infrahub.yml": CONFIG_WITH_OBJECTS, "objects/tags.yml": _object_file("pc-promoted-tag")},
            "Release v2 with objects",
        )
        remote.tag("v2", v2_sha)

        branch = await client.branch.create(branch_name="promo-via-pc")

        repo_in_branch = await client.get(kind=InfrahubKind.READONLYREPOSITORY, id=node_id, branch=branch.name)
        repo_in_branch.ref.value = "v2"
        await repo_in_branch.save()
        await import_read_only_repository_last_commit(
            model=GitReadOnlyRepositoryImportCommit(
                repository_id=node_id,
                repository_name=repo_name,
                repository_kind=InfrahubKind.READONLYREPOSITORY,
                infrahub_branch_name=branch.name,
                ref="v2",
            )
        )

        # Isolation while under review: the branch advanced, the primary branch did not.
        repo_branch: CoreReadOnlyRepository = await NodeManager.get_one(
            db=db, id=node_id, kind=InfrahubKind.READONLYREPOSITORY, branch=branch.name, raise_on_error=True
        )
        assert repo_branch.commit.value == v2_sha
        assert await _recorded_commit(db, node_id) == v1_sha

        proposed_change = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={"source_branch": branch.name, "destination_branch": "main", "name": "promote v2"},
        )
        await proposed_change.save()

        proposed_change.state.value = ProposedChangeState.MERGED.value
        await proposed_change.save()

        # Promotion after the merge: the primary branch carries the new commit and the content.
        assert await _recorded_commit(db, node_id) == v2_sha
        tags = await client.filters(kind="BuiltinTag", name__value="pc-promoted-tag")
        assert len(tags) == 1

    async def test_unrelated_proposed_change_merge_preserves_promoted_ref(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
        prefect_test_fixture: None,
        bus_simulator: BusSimulator,
    ) -> None:
        """Merging an unrelated proposed change must not move the repository's pin.

        The proposed change is opened while the consumer is pinned at the previous release, and the
        consumer is promoted on the primary branch while it is under review. Before the merge the
        branch reads a stale snapshot of the repository (asserted below). Every branch merge
        dispatches a repository merge for every read-only repository, but the dispatch runs after
        the graph merge, where the branch's unmodified repository node resolves to the primary
        branch's current values — so the ref/commit copy compares equal and the promotion survives.
        The dispatched flow is executed explicitly here, standing in for the task worker that runs
        it in a real deployment; running that flow against an UNMERGED stale branch would roll the
        promotion back, which is why this guard pins the full merge-then-dispatch sequence.
        """
        remote = _SeededRemote(tmp_path)
        v1_sha = remote.branch_tip()
        remote.tag("v1", v1_sha)

        repo_name = "promo-stale-branch-repo"
        node_id = await _register_readonly(client, repo_name, str(remote.bare_path), "v1")
        await _import_ref(node_id, repo_name, "v1")
        assert await _recorded_commit(db, node_id) == v1_sha

        # The unrelated branch and its proposed change both predate the promotion.
        stale_branch = await client.branch.create(branch_name="unrelated-work")
        unrelated = await client.create(kind="BuiltinTag", data={"name": "unrelated-change"}, branch=stale_branch.name)
        await unrelated.save()
        proposed_change = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={"source_branch": stale_branch.name, "destination_branch": "main", "name": "unrelated work"},
        )
        await proposed_change.save()

        # The consumer is promoted to v2 on the primary branch while the PC is under review.
        v2_sha = remote.commit_files({"release.txt": "v2 content\n"}, "Release v2")
        remote.tag("v2", v2_sha)
        await _bump_ref(client, node_id, repo_name, "v2")
        assert await _recorded_commit(db, node_id) == v2_sha

        # The branch's snapshot of the repository is stale: it predates the promotion.
        repo_on_branch = await client.get(kind=InfrahubKind.READONLYREPOSITORY, id=node_id, branch=stale_branch.name)
        assert repo_on_branch.ref.value == "v1"

        proposed_change.state.value = ProposedChangeState.MERGED.value
        await proposed_change.save()

        # Control: the merge genuinely happened - the unrelated change arrived on the primary branch.
        merged_tags = await client.filters(kind="BuiltinTag", name__value="unrelated-change")
        assert len(merged_tags) == 1

        # Execute the repository merge the branch merge dispatches for this read-only repository,
        # as the task worker would in a real deployment.
        await merge_git_repository(
            model=GitRepositoryMerge(
                repository_id=node_id,
                repository_name=repo_name,
                internal_status="active",
                source_branch=stale_branch.name,
                destination_branch="main",
                destination_branch_id=str(stale_branch.id),
                repository_kind=InfrahubKind.READONLYREPOSITORY,
            )
        )

        # Intended contract: the unrelated merge leaves the promotion untouched.
        repo_after: CoreReadOnlyRepository = await NodeManager.get_one(
            db=db, id=node_id, kind=InfrahubKind.READONLYREPOSITORY, raise_on_error=True
        )
        assert repo_after.ref.value == "v2"
        assert repo_after.commit.value == v2_sha

    async def test_branch_ref_reimport_staged_in_branch_promotes_via_proposed_change(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
        prefect_test_fixture: None,
        bus_simulator: BusSimulator,
    ) -> None:
        """The branch-pinned promotion flow: reimport staged in a branch, merged via a proposed change.

        The common environment-chain variant: the consumer's ref is its environment's git branch and
        never changes. When the git branch advances (a promotion lands on the git host), the operator
        creates an Infrahub branch, triggers the last-commit reimport on it — the import loads the
        branch tip there while the primary branch provably keeps the previous state — and the change
        lands through a proposed change, whose merge carries the recorded commit and the imported
        content onto the primary branch.
        """
        remote = _SeededRemote(tmp_path)
        tip1 = remote.branch_tip()

        repo_name = "promo-branch-flow-repo"
        node_id = await _register_readonly(client, repo_name, str(remote.bare_path), SOURCE_BRANCH)
        await _import_ref(node_id, repo_name, SOURCE_BRANCH)
        assert await _recorded_commit(db, node_id) == tip1

        # A promotion lands on the environment's git branch (e.g. a pull request was merged).
        tip2 = remote.commit_files(
            {".infrahub.yml": CONFIG_WITH_OBJECTS, "objects/tags.yml": _object_file("branch-flow-tag")},
            "Promotion landed on the environment branch",
        )

        # Stage the reimport in an Infrahub branch — the ref itself never changes.
        staging = await client.branch.create(branch_name="promote-next")
        await import_read_only_repository_last_commit(
            model=GitReadOnlyRepositoryImportCommit(
                repository_id=node_id,
                repository_name=repo_name,
                repository_kind=InfrahubKind.READONLYREPOSITORY,
                infrahub_branch_name=staging.name,
                ref=SOURCE_BRANCH,
            )
        )

        # Isolation while under review: the branch advanced to the tip, the primary branch did not.
        repo_branch: CoreReadOnlyRepository = await NodeManager.get_one(
            db=db, id=node_id, kind=InfrahubKind.READONLYREPOSITORY, branch=staging.name, raise_on_error=True
        )
        assert repo_branch.commit.value == tip2
        assert await _recorded_commit(db, node_id) == tip1

        proposed_change = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={"source_branch": staging.name, "destination_branch": "main", "name": "promote next release"},
        )
        await proposed_change.save()
        proposed_change.state.value = ProposedChangeState.MERGED.value
        await proposed_change.save()

        # Promotion after the merge: the primary branch carries the reviewed tip and its content.
        assert await _recorded_commit(db, node_id) == tip2
        tags = await client.filters(kind="BuiltinTag", name__value="branch-flow-tag")
        assert len(tags) == 1

    async def test_reimport_follows_force_pushed_branch_ref(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        tmp_path: Path,
    ) -> None:
        """A consumer pinned to a branch ref lands on the rewritten tip after a force-push + reimport.

        The read-only analogue of upstream history rewrites: a botched promotion gets force-fixed on
        the tracked branch. Branch remote-tracking refs are force-updated on fetch (unlike tags), so
        the reimport must converge on the rewritten tip.
        """
        remote = _SeededRemote(tmp_path)
        original_tip = remote.branch_tip()

        repo_name = "promo-force-branch-repo"
        node_id = await _register_readonly(client, repo_name, str(remote.bare_path), SOURCE_BRANCH)
        await _import_ref(node_id, repo_name, SOURCE_BRANCH)
        assert await _recorded_commit(db, node_id) == original_tip

        rewritten_tip = remote.rewrite_branch_history()
        assert rewritten_tip != original_tip

        await _import_ref(node_id, repo_name, SOURCE_BRANCH)
        assert await _recorded_commit(db, node_id) == rewritten_tip
