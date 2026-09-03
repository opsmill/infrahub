"""A node save must leave every vertex's metadata equal to what its level-1 edges imply.

Any changes to an object or its attributes or relationships visible on the default or global
branches must update the appropriate metadata: ``created_at``/``created_by`` and
``updated_at``/``updated_by`` on Node, Attribute, and Relationship vertices.
"""

from dataclasses import dataclass
from enum import Enum, auto

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.schema.agnostic_retirement import WIDGET_KIND
from tests.helpers.schema.branch_support_mismatch import register_branch_support_mismatch_schemas
from tests.helpers.vertex_metadata import (
    assert_vertex_metadata_matches_recompute,
    get_node_vertex_element_ids,
    get_vertex_user_metadata,
)

CREATOR = "creator"
UPDATER = "updater"
DELETER = "deleter"

MIRROR_KIND = "TestMetaMirror"
MIRROR_PEER_KIND = "TestMetaMirrorPeer"
REPOSITORY_KIND = "CoreReadOnlyRepository"
TAG_KIND = "BuiltinTag"

DEFAULT_WRITE = "default"
USER_WRITE = "user"


@pytest.fixture
async def metadata_schemas(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    register_branch_support_mismatch_schemas(branch=default_branch)


async def _write_branch(db: InfrahubDatabase, default_branch: Branch, write_branch: str) -> Branch:
    if write_branch == DEFAULT_WRITE:
        return default_branch
    return await create_branch(branch_name="metadata-writer", db=db)


class Mismatch(Enum):
    """A kind whose branch support disagrees with that of one of its fields."""

    AWARE_NODE_AGNOSTIC_RELATIONSHIP = auto()
    AWARE_NODE_AGNOSTIC_ATTRIBUTE = auto()
    AGNOSTIC_NODE_AWARE_ATTRIBUTE = auto()
    AGNOSTIC_NODE_LOCAL_ATTRIBUTE = auto()


WRITE_BRANCHES = (DEFAULT_WRITE, USER_WRITE)


@dataclass(frozen=True)
class MismatchCell:
    """One mismatch exercised by one operation, written from one branch."""

    mismatch: Mismatch
    operation: str
    write_branch: str

    @property
    def name(self) -> str:
        return f"{self.mismatch.name.lower().replace('_', '-')}-{self.operation}-on-{self.write_branch}"


async def _repository_update(db: InfrahubDatabase, default_branch: Branch, write_branch: str) -> None:
    """Change the aware ``ref`` and ``commit`` of an agnostic repository, then read it on the default branch.

    Each attribute's edge lands on the writer's own branch, so a change written from a feature branch
    is invisible on the default branch and must leave the default-branch metadata where it was; the
    same change written on the default branch is visible and must move it.
    """
    repository = await Node.init(db=db, schema=REPOSITORY_KIND, branch=default_branch)
    await repository.new(db=db, name="mirror", location="/repositories/mirror", ref="main")
    await repository.save(db=db, user_id=CREATOR)

    branch = await _write_branch(db=db, default_branch=default_branch, write_branch=write_branch)
    on_write_branch = await NodeManager.get_one(db=db, branch=branch, id=repository.get_id(), raise_on_error=True)
    on_write_branch.get_attribute(name="ref").value = "stable"
    on_write_branch.get_attribute(name="commit").value = "0123456789abcdef0123456789abcdef01234567"
    await on_write_branch.save(db=db, user_id=UPDATER)
    assert {"ref", "commit"} <= set(on_write_branch.node_changelog.updated_fields)

    on_default = await NodeManager.get_one(db=db, branch=default_branch, id=repository.get_id(), raise_on_error=True)
    written_on_default = write_branch == DEFAULT_WRITE
    assert on_default.get_attribute(name="ref").value == ("stable" if written_on_default else "main")
    assert on_default.get_attribute(name="commit").value == (
        "0123456789abcdef0123456789abcdef01234567" if written_on_default else None
    )

    await assert_vertex_metadata_matches_recompute(
        db=db, element_id=on_default.db_id, description=f"{REPOSITORY_KIND} {repository.get_id()}"
    )


async def _widget_delete(db: InfrahubDatabase, default_branch: Branch, write_branch: str) -> None:
    """Delete an aware widget carrying an agnostic attribute, then check the default-branch view.

    Deletion resolves an agnostic attribute of an aware node to the node's own branch rather than to
    ``-global-``, so a deletion from a feature branch writes no level-1 edge anywhere: the default
    branch still sees the whole object, and not one vertex property may move. The same deletion on
    the default branch does write level-1 edges, and the vertex must record it before it leaves the
    default branch.
    """
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await widget.new(db=db, name="widget", serial=1)
    await widget.save(db=db, user_id=CREATOR)

    element_ids = await get_node_vertex_element_ids(db=db, node_uuid=widget.get_id())
    assert len(element_ids) == 1
    element_id = element_ids[0]
    before_delete = await get_vertex_user_metadata(db=db, element_id=element_id)
    assert before_delete.updated_by == CREATOR

    branch = await _write_branch(db=db, default_branch=default_branch, write_branch=write_branch)
    on_write_branch = await NodeManager.get_one(db=db, branch=branch, id=widget.get_id(), raise_on_error=True)
    await on_write_branch.delete(db=db, user_id=DELETER)
    assert on_write_branch.node_changelog.updated_fields

    after_delete = await get_vertex_user_metadata(db=db, element_id=element_id)
    on_default = await NodeManager.get_one(db=db, branch=default_branch, id=widget.get_id())
    visible = on_default is not None
    assert visible == (write_branch == USER_WRITE)

    if not visible:
        assert after_delete.created_at == before_delete.created_at
        assert after_delete.created_by == before_delete.created_by
        assert after_delete.updated_by == DELETER
        assert after_delete.updated_at is not None
        assert before_delete.updated_at is not None
        assert after_delete.updated_at > before_delete.updated_at
        await assert_vertex_metadata_matches_recompute(
            db=db, element_id=element_id, description=f"deleted {WIDGET_KIND} {widget.get_id()}"
        )
        return

    assert on_default is not None
    assert on_default.get_attribute(name="name").value == "widget"
    assert on_default.get_attribute(name="serial").value == 1

    assert after_delete == before_delete
    await assert_vertex_metadata_matches_recompute(
        db=db, element_id=element_id, description=f"{WIDGET_KIND} {widget.get_id()}"
    )


async def _widget_update(db: InfrahubDatabase, default_branch: Branch, write_branch: str) -> None:
    """Change the agnostic ``serial`` of an aware widget, then read it on the default branch.

    An agnostic attribute writes on the global branch whichever branch the writer is on, so the new
    value is what every branch reads and the object's metadata has to move with it. Writing from a
    feature branch and writing on the default branch are the same level-1 write here, and both arms
    assert the move.
    """
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await widget.new(db=db, name=f"updated-widget-{write_branch}", serial=1)
    await widget.save(db=db, user_id=CREATOR)

    before = await get_vertex_user_metadata(db=db, element_id=widget.db_id)
    assert before.updated_by == CREATOR

    branch = await _write_branch(db=db, default_branch=default_branch, write_branch=write_branch)
    on_write_branch = await NodeManager.get_one(db=db, branch=branch, id=widget.get_id(), raise_on_error=True)
    on_write_branch.get_attribute(name="serial").value = 2
    await on_write_branch.save(db=db, user_id=UPDATER)
    assert "serial" in on_write_branch.node_changelog.updated_fields

    on_default = await NodeManager.get_one(db=db, branch=default_branch, id=widget.get_id(), raise_on_error=True)
    assert on_default.get_attribute(name="serial").value == 2, "an agnostic attribute is read by every branch"

    after = await assert_vertex_metadata_matches_recompute(
        db=db, element_id=on_default.db_id, description=f"{WIDGET_KIND} {widget.get_id()}"
    )
    assert after.updated_by == UPDATER
    assert before.updated_at is not None
    assert after.updated_at is not None
    assert after.updated_at > before.updated_at


CELL_RUNNERS = {
    (Mismatch.AGNOSTIC_NODE_AWARE_ATTRIBUTE, "update"): _repository_update,
    (Mismatch.AWARE_NODE_AGNOSTIC_ATTRIBUTE, "update"): _widget_update,
    (Mismatch.AWARE_NODE_AGNOSTIC_ATTRIBUTE, "delete"): _widget_delete,
}

MISMATCH_CELLS = [
    MismatchCell(mismatch=mismatch, operation=operation, write_branch=write_branch)
    for mismatch, operation in CELL_RUNNERS
    for write_branch in WRITE_BRANCHES
]


@pytest.mark.parametrize("cell", MISMATCH_CELLS, ids=lambda cell: cell.name)
async def test_node_save_leaves_metadata_equal_to_the_recompute(
    db: InfrahubDatabase, default_branch: Branch, metadata_schemas: None, cell: MismatchCell
) -> None:
    await CELL_RUNNERS[cell.mismatch, cell.operation](
        db=db, default_branch=default_branch, write_branch=cell.write_branch
    )


# ---------------------------------------------------------------------------
# Pins for the vertices the invariant deliberately excludes
# ---------------------------------------------------------------------------


async def test_agnostic_change_from_a_branch_leaves_a_node_deleted_on_default_alone(
    db: InfrahubDatabase, default_branch: Branch, metadata_schemas: None
) -> None:
    """A node deleted on the default branch stops taking metadata from later agnostic writes.

    A branch created before the deletion can still write the node's agnostic attribute, and that
    write lands at level 1. The node is gone from the default branch all the same, so no reader can
    see the change and the vertex must keep the metadata it had when it was deleted.

    The attribute vertex is the contrast: it is shared with the branch that can still read it, the
    write reaches it at level 1, and it does take the change.
    """
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await widget.new(db=db, name="widget", serial=1)
    await widget.save(db=db, user_id=CREATOR)

    branch = await create_branch(branch_name="before-the-delete", db=db)
    on_branch = await NodeManager.get_one(db=db, branch=branch, id=widget.get_id(), raise_on_error=True)

    on_default = await NodeManager.get_one(db=db, branch=default_branch, id=widget.get_id(), raise_on_error=True)
    await on_default.delete(db=db, user_id=DELETER)

    element_id = (await get_node_vertex_element_ids(db=db, node_uuid=widget.get_id()))[0]
    after_delete = await get_vertex_user_metadata(db=db, element_id=element_id)

    serial_element_id = on_branch.get_attribute(name="serial").db_id
    serial_before = await get_vertex_user_metadata(db=db, element_id=serial_element_id)

    on_branch.get_attribute(name="serial").value = 2
    await on_branch.save(db=db, user_id=UPDATER)
    assert "serial" in on_branch.node_changelog.updated_fields

    assert await get_vertex_user_metadata(db=db, element_id=element_id) == after_delete

    serial_after = await get_vertex_user_metadata(db=db, element_id=serial_element_id)
    assert serial_after.updated_by == UPDATER
    assert serial_before.updated_at is not None
    assert serial_after.updated_at is not None
    assert serial_after.updated_at > serial_before.updated_at
    await assert_vertex_metadata_matches_recompute(
        db=db, element_id=serial_element_id, description=f"serial attribute of {widget.get_id()}"
    )


async def test_agnostic_change_from_a_branch_leaves_a_migrated_out_twin_alone(
    db: InfrahubDatabase, default_branch: Branch, metadata_schemas: None
) -> None:
    """A kind migration leaves two vertices on one uuid; only the surviving one takes metadata.

    The migrated-out vertex keeps the uuid and the field vertices, so it stays reachable from every
    query that addresses the node by uuid, and only the state of its ``IS_PART_OF`` edges says it is
    no longer the node the default branch returns.
    """
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await widget.new(db=db, name="widget", serial=1)
    await widget.save(db=db, user_id=CREATOR)

    await _migrate_kind_namespace(db=db, branch=default_branch, kind=WIDGET_KIND, new_name="Widget")

    element_ids = await get_node_vertex_element_ids(db=db, node_uuid=widget.get_id())
    assert len(element_ids) == 2
    migrated_out = widget.db_id
    (surviving,) = [element_id for element_id in element_ids if element_id != migrated_out]
    migrated_out_before = await get_vertex_user_metadata(db=db, element_id=migrated_out)

    branch = await create_branch(branch_name="after-the-migration", db=db)
    on_branch = await NodeManager.get_one(db=db, branch=branch, id=widget.get_id(), raise_on_error=True)
    on_branch.get_attribute(name="serial").value = 2
    await on_branch.save(db=db, user_id=UPDATER)
    assert "serial" in on_branch.node_changelog.updated_fields

    assert await get_vertex_user_metadata(db=db, element_id=migrated_out) == migrated_out_before
    await assert_vertex_metadata_matches_recompute(
        db=db, element_id=migrated_out, description=f"migrated-out twin of {widget.get_id()}"
    )
    await assert_vertex_metadata_matches_recompute(
        db=db, element_id=surviving, description=f"surviving twin of {widget.get_id()}"
    )


async def test_a_default_branch_change_to_an_agnostic_node_leaves_a_migrated_out_twin_alone(
    db: InfrahubDatabase, default_branch: Branch, metadata_schemas: None
) -> None:
    """An agnostic kind records its migration on the global branch, not on the branch it ran on.

    The migrated-out vertex of an agnostic kind carries its ``deleted`` ``IS_PART_OF`` edge on the
    global branch, so every guard that has to recognise the twin must key on the branch level rather
    than on a branch name.
    """
    mirror = await Node.init(db=db, schema=MIRROR_KIND, branch=default_branch)
    await mirror.new(db=db, name="mirror", ref="main")
    await mirror.save(db=db, user_id=CREATOR)

    await _migrate_kind_namespace(db=db, branch=default_branch, kind=MIRROR_KIND, new_name="MetaMirror")

    element_ids = await get_node_vertex_element_ids(db=db, node_uuid=mirror.get_id())
    assert len(element_ids) == 2
    migrated_out = mirror.db_id
    (surviving,) = [element_id for element_id in element_ids if element_id != migrated_out]
    migrated_out_before = await get_vertex_user_metadata(db=db, element_id=migrated_out)

    on_default = await NodeManager.get_one(db=db, branch=default_branch, id=mirror.get_id(), raise_on_error=True)
    on_default.get_attribute(name="ref").value = "stable"
    await on_default.save(db=db, user_id=UPDATER)
    assert "ref" in on_default.node_changelog.updated_fields

    assert await get_vertex_user_metadata(db=db, element_id=migrated_out) == migrated_out_before
    await assert_vertex_metadata_matches_recompute(
        db=db, element_id=migrated_out, description=f"migrated-out twin of {mirror.get_id()}"
    )
    await assert_vertex_metadata_matches_recompute(
        db=db, element_id=surviving, description=f"surviving twin of {mirror.get_id()}"
    )


async def test_deleting_an_agnostic_node_with_only_aware_fields_from_a_branch_writes_no_metadata(
    db: InfrahubDatabase, default_branch: Branch, metadata_schemas: None
) -> None:
    """Every field edge of this deletion lands on the writer's branch, so nothing may be stamped.

    The kind is agnostic, so the node itself leaves the default branch, but none of its fields
    wrote a level-1 edge. A gate reading the node's branch support rather than the edges it wrote
    stamps the vertex regardless.
    """
    mirror = await Node.init(db=db, schema=MIRROR_KIND, branch=default_branch)
    await mirror.new(db=db, name="mirror", ref="main")
    await mirror.save(db=db, user_id=CREATOR)

    element_id = (await get_node_vertex_element_ids(db=db, node_uuid=mirror.get_id()))[0]
    before_delete = await get_vertex_user_metadata(db=db, element_id=element_id)

    branch = await create_branch(branch_name="metadata-writer", db=db)
    on_branch = await NodeManager.get_one(db=db, branch=branch, id=mirror.get_id(), raise_on_error=True)
    await on_branch.delete(db=db, user_id=DELETER)
    assert on_branch.node_changelog.updated_fields

    assert await get_vertex_user_metadata(db=db, element_id=element_id) == before_delete


async def test_deleting_an_agnostic_node_with_a_relationship_from_a_branch_writes_metadata(
    db: InfrahubDatabase, default_branch: Branch, metadata_schemas: None
) -> None:
    """A relationship of an agnostic node is deleted globally, so removing it is visible by default."""
    mirror = await Node.init(db=db, schema=MIRROR_KIND, branch=default_branch)
    await mirror.new(db=db, name="peer-target", ref="main")
    await mirror.save(db=db, user_id=CREATOR)

    peer = await Node.init(db=db, schema=MIRROR_PEER_KIND, branch=default_branch)
    await peer.new(db=db, name="peer-holder", mirror=mirror)
    await peer.save(db=db, user_id=CREATOR)

    element_id = (await get_node_vertex_element_ids(db=db, node_uuid=peer.get_id()))[0]
    before_delete = await get_vertex_user_metadata(db=db, element_id=element_id)

    branch = await create_branch(branch_name="relationship-remover", db=db)
    on_branch = await NodeManager.get_one(db=db, branch=branch, id=peer.get_id(), raise_on_error=True)
    await on_branch.delete(db=db, user_id=DELETER)

    after_delete = await get_vertex_user_metadata(db=db, element_id=element_id)
    assert after_delete != before_delete, "the globally-removed relationship left the vertex metadata behind"
    assert after_delete.updated_by == DELETER


async def test_a_default_branch_save_leaves_every_field_vertex_equal_to_the_recompute(
    db: InfrahubDatabase, default_branch: Branch, metadata_schemas: None
) -> None:
    """The invariant covers the Attribute and Relationship vertices, not only the Node vertex."""
    tag = await Node.init(db=db, schema=TAG_KIND, branch=default_branch)
    await tag.new(db=db, name="metadata-tag")
    await tag.save(db=db, user_id=CREATOR)

    repository = await Node.init(db=db, schema=REPOSITORY_KIND, branch=default_branch)
    await repository.new(db=db, name="fields", location="/repositories/fields", ref="main", tags=[tag])
    await repository.save(db=db, user_id=CREATOR)

    on_default = await NodeManager.get_one(db=db, branch=default_branch, id=repository.get_id(), raise_on_error=True)
    on_default.get_attribute(name="ref").value = "stable"
    await on_default.save(db=db, user_id=UPDATER)

    for name in ("name", "location", "ref"):
        stored = await assert_vertex_metadata_matches_recompute(
            db=db,
            element_id=on_default.get_attribute(name=name).db_id,
            description=f"{name} attribute of {repository.get_id()}",
        )
        assert stored.created_by == CREATOR
        assert stored.updated_at is not None

    for peer in await on_default.get_relationship(name="tags").get_relationships(db=db):
        stored = await assert_vertex_metadata_matches_recompute(
            db=db, element_id=peer.db_id, description=f"tags relationship of {repository.get_id()}"
        )
        assert stored.created_by == CREATOR
        assert stored.updated_at is not None

    await assert_vertex_metadata_matches_recompute(
        db=db, element_id=on_default.db_id, description=f"{REPOSITORY_KIND} {repository.get_id()}"
    )


async def _migrate_kind_namespace(db: InfrahubDatabase, branch: Branch, kind: str, new_name: str) -> None:
    """Move ``kind`` into the ``Test2`` namespace on ``branch``, replacing its Node vertex with a second one."""
    new_kind = f"Test2{new_name}"
    schema = registry.schema.get_schema_branch(name=branch.name)
    candidate_schema = schema.duplicate()
    node_schema = candidate_schema.get(name=kind)
    candidate_schema.delete(name=kind)
    node_schema.name = new_name
    node_schema.namespace = "Test2"
    candidate_schema.set(name=new_kind, schema=node_schema)

    migration = NodeKindUpdateMigration(
        previous_node_schema=schema.get(name=kind),
        new_node_schema=node_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=new_kind, field_name="namespace"),
    )
    execution_result = await migration.execute(
        migration_input=MigrationInput(db=db, at=Timestamp(), user_id="migration-user"), branch=branch
    )
    assert not execution_result.errors

    registry.schema.set_schema_branch(name=branch.name, schema=candidate_schema)
