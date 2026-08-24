"""Removing a branch-agnostic field from the schema releases its value, unless a branch still reads it.

A schema update that removes a field is specific to a branch, even when the field being removed is
branch-agnostic. In this case, the schema migration hides the field by writing a branch-scoped
`deleted` edge and leaves the global edges of the just-deleted field open. The schema migration must
close the edges on the global branch only if the field is no longer reachable on ANY branch.

Every assertion reads the edges directly rather than going through the node manager: the subject is
which edges carry a `to` timestamp and which do not, and a read through the manager would hide the
states these tests exist to pin down. Where a branch is expected to go on reading the field, the
manager is used as well, because that is the claim being made.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.database.validation import verify_graph
import pytest

from infrahub.core import registry
from infrahub.core.constants import GLOBAL_BRANCH_NAME, SYSTEM_USER_ID, HashableModelState, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_attribute_remove import NodeAttributeRemoveMigration
from infrahub.core.migrations.schema.node_relationship_remove import NodeRelationshipRemoveMigration
from infrahub.core.migrations.shared import MigrationInput, MigrationResult
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.rollback import RollbackScope
from infrahub.core.rollback import GraphRollbacker
from infrahub.core.timestamp import Timestamp
from tests.helpers.agnostic_edges import (
    VertexMetadata,
    assert_attribute_retired_at,
    assert_relationship_retired_at,
    attribute_global_edges,
    attribute_metadata,
    attribute_owning_edges,
    edge_summary,
    open_edge_types,
    open_edges,
    relationship_global_edges,
    relationship_metadata,
    relationship_peer_shape,
    to_times,
)
from tests.helpers.db_validation import get_node_metadata
from tests.helpers.schema.agnostic_retirement import (
    AGNOSTIC_RETIREMENT_SCHEMA,
    BEACON_KIND,
    GADGET_KIND,
    RELATIONSHIP_IDENTIFIER,
    WIDGET_KIND,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

ATTRIBUTE_NAME = "serial"
RELATIONSHIP_NAME = "gadget"


@pytest.fixture
async def agnostic_schema(db: InfrahubDatabase, default_branch: Branch) -> None:
    registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)


@pytest.fixture(autouse=True)
async def verify_graph_invariants(db: InfrahubDatabase, default_branch: Branch) -> AsyncIterator[None]:
    """Check the whole-graph invariants after every test in this module."""
    yield
    await verify_graph(db=db)


async def _create_widget(db: InfrahubDatabase, branch: Branch, name: str, serial: int, **kwargs: Any) -> Node:
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=branch)
    await widget.new(db=db, name=name, serial=serial, **kwargs)
    await widget.save(db=db)
    return widget


async def _create_gadget(db: InfrahubDatabase, branch: Branch, name: str) -> Node:
    gadget = await Node.init(db=db, schema=GADGET_KIND, branch=branch)
    await gadget.new(db=db, name=name)
    await gadget.save(db=db)
    return gadget


async def _delete(db: InfrahubDatabase, node_id: str, branch: Branch, at: Timestamp) -> None:
    to_delete = await NodeManager.get_one(db=db, id=node_id, branch=branch, raise_on_error=True)
    await to_delete.delete(db=db, at=at)


async def _remove_attribute_from_schema(
    db: InfrahubDatabase,
    branch: Branch,
    at: Timestamp,
    kind: str = WIDGET_KIND,
    attribute_name: str = ATTRIBUTE_NAME,
) -> MigrationResult:
    """Run the attribute-removal migration for a branch-agnostic attribute on `branch`."""
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema_branch.get(name=kind)

    candidate = schema_branch.duplicate()
    node_schema = candidate.get(name=kind)
    node_schema.get_attribute(name=attribute_name).state = HashableModelState.ABSENT
    candidate.set(name=kind, schema=node_schema)
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)

    migration = NodeAttributeRemoveMigration(
        previous_node_schema=previous_node,
        new_node_schema=node_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name=attribute_name),
    )
    return await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=branch)


async def _create_beacon(db: InfrahubDatabase, branch: Branch, name: str, serial: int) -> Node:
    beacon = await Node.init(db=db, schema=BEACON_KIND, branch=branch)
    await beacon.new(db=db, name=name, serial=serial)
    await beacon.save(db=db)
    return beacon


async def _remove_relationship_from_schema(db: InfrahubDatabase, branch: Branch, at: Timestamp) -> MigrationResult:
    """Run the relationship-removal migration for the widget's branch-agnostic relationship on `branch`.

    Both sides of the identifier are dropped from the registered schema first, which is what the schema
    update pipeline has already done by the time migrations run. Leaving one side in place would make
    the migration skip every vertex.
    """
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema_branch.get(name=WIDGET_KIND)
    identifier = previous_node.get_relationship(name=RELATIONSHIP_NAME).get_identifier()

    candidate = schema_branch.duplicate()
    for sharing_schema in candidate.get_schemas_by_rel_identifier(identifier=identifier):
        node_schema = candidate.get(name=sharing_schema.kind)
        node_schema.relationships = [rel for rel in node_schema.relationships if rel.identifier != identifier]
        candidate.set(name=sharing_schema.kind, schema=node_schema)
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)

    migration = NodeRelationshipRemoveMigration(
        previous_node_schema=previous_node,
        new_node_schema=candidate.get(name=WIDGET_KIND),
        schema_path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind=WIDGET_KIND, field_name=RELATIONSHIP_NAME
        ),
    )
    return await migration.execute(migration_input=MigrationInput(db=db, at=at), branch=branch)


async def test_an_attribute_removed_from_the_schema_is_closed_when_no_branch_declares_it(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """No branch forked while the attribute existed, so the removal leaves nothing able to read it."""
    widget = await _create_widget(db=db, branch=default_branch, name="loses-its-serial", serial=100)

    before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

    removed_at = Timestamp()
    result = await _remove_attribute_from_schema(db=db, branch=default_branch, at=removed_at)
    assert not result.errors
    assert result.nbr_migrations_executed == 1

    after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert_attribute_retired_at(after=after, before=before, at=removed_at)

    owning_edges = await attribute_owning_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert sorted((edge.branch, edge.status, edge.to_time or "") for edge in owning_edges) == [
        (GLOBAL_BRANCH_NAME, "active", removed_at.to_string()),
        (default_branch.name, "deleted", ""),
    ], "the removal's own branch-scoped tombstone is left exactly as it was; only the global edge is closed"


async def test_a_relationship_removed_from_the_schema_is_closed_when_no_branch_declares_it(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """Both peers survive the removal, but no branch can still reach them over a live global edge."""
    gadget = await _create_gadget(db=db, branch=default_branch, name="keeps-existing")
    widget = await _create_widget(db=db, branch=default_branch, name="loses-its-gadget", serial=200, gadget=gadget)

    before = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
    assert [edge.edge_type for edge in open_edges(before)].count("IS_RELATED") == 2

    removed_at = Timestamp()
    result = await _remove_relationship_from_schema(db=db, branch=default_branch, at=removed_at)
    assert not result.errors
    assert result.nbr_migrations_executed == 1

    after = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
    assert_relationship_retired_at(after=after, before=before, at=removed_at)
    assert await NodeManager.get_one(db=db, id=gadget.id, branch=default_branch) is not None, (
        "the peer object is untouched; only the relationship between the two was released"
    )


async def test_an_attribute_stays_open_for_a_branch_that_forked_before_the_removal(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """The branch still declares the attribute and still holds the object, so the value is not released."""
    widget = await _create_widget(db=db, branch=default_branch, name="serial-kept-by-a-fork", serial=300)
    branch = await create_branch(db=db, branch_name="declares-the-attribute-still")

    before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

    result = await _remove_attribute_from_schema(db=db, branch=default_branch, at=Timestamp())
    assert not result.errors
    assert result.nbr_migrations_executed == 1

    after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert edge_summary(after) == edge_summary(before), "the branch retains the field, so nothing is released"

    on_branch = await NodeManager.get_one(db=db, id=widget.id, branch=branch)
    assert on_branch is not None
    assert on_branch.get_attribute(name=ATTRIBUTE_NAME).value == 300


async def test_a_relationship_stays_open_for_a_branch_that_forked_before_the_removal(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """The branch still declares the relationship and still reads both of its peers as live."""
    gadget = await _create_gadget(db=db, branch=default_branch, name="peer-kept-by-a-fork")
    widget = await _create_widget(db=db, branch=default_branch, name="gadget-kept-by-a-fork", serial=400, gadget=gadget)
    branch = await create_branch(db=db, branch_name="declares-the-relationship-still")

    before = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
    assert [edge.edge_type for edge in open_edges(before)].count("IS_RELATED") == 2

    result = await _remove_relationship_from_schema(db=db, branch=default_branch, at=Timestamp())
    assert not result.errors
    assert result.nbr_migrations_executed == 1

    after = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
    assert edge_summary(after) == edge_summary(before), "the branch retains the relationship, so nothing is released"
    assert await relationship_peer_shape(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER) == (2, 2)

    on_branch = await NodeManager.get_one(db=db, id=widget.id, branch=branch)
    assert on_branch is not None
    rel_mngr = on_branch.get_relationship("gadget")
    peers = await rel_mngr.get_relationships(db=db)
    assert len(peers) == 1
    peer = peers[0]
    assert peer.get_peer_id() == gadget.id


async def test_one_removal_closes_only_the_objects_the_fork_cannot_reach(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """Two objects of one kind, one retained and one not, released by a single removal.

    To-be-retained object is created on the default branch, then a branch is forked, then the
    to-be-retired object is created on the default branch, so to-be-retired is only visible on
    the default. When the schema migration runs, the attribute on to-be-retired is not accessible
    from any branch and needs to be closed.
    """
    retained = await _create_widget(db=db, branch=default_branch, name="held-by-the-fork", serial=800)
    branch = await create_branch(db=db, branch_name="forked-between-the-two")
    # created after the branch, so only visible on the default branch, not on the user branch
    retired = await _create_widget(db=db, branch=default_branch, name="created-after-the-fork", serial=900)

    retained_before = await attribute_global_edges(db=db, node_id=retained.id, attribute_name=ATTRIBUTE_NAME)
    retired_before = await attribute_global_edges(db=db, node_id=retired.id, attribute_name=ATTRIBUTE_NAME)
    assert open_edge_types(retained_before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}
    assert open_edge_types(retired_before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

    removed_at = Timestamp()
    result = await _remove_attribute_from_schema(db=db, branch=default_branch, at=removed_at)
    assert not result.errors
    assert result.nbr_migrations_executed == 2, "both objects went through the one removal, as one batch"

    retained_after = await attribute_global_edges(db=db, node_id=retained.id, attribute_name=ATTRIBUTE_NAME)
    assert edge_summary(retained_after) == edge_summary(retained_before), (
        "the fork holds this object and still declares the attribute, so nothing is released"
    )
    assert to_times(retained_after) == {None}

    retired_after = await attribute_global_edges(db=db, node_id=retired.id, attribute_name=ATTRIBUTE_NAME)
    assert_attribute_retired_at(after=retired_after, before=retired_before, at=removed_at)

    on_branch = await NodeManager.get_one(db=db, id=retained.id, branch=branch)
    assert on_branch is not None
    assert on_branch.get_attribute(name=ATTRIBUTE_NAME).value == 800, (
        "the branch that keeps its value read for real is the one the value was kept for"
    )
    assert await NodeManager.get_one(db=db, id=retired.id, branch=branch) is None, (
        "the other object was created after the fork, so no branch outside the removing one holds it"
    )


async def test_a_relationship_is_closed_when_the_only_fork_reads_one_of_its_peers_as_live(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """Test agnostic relationship is only removed when it is dead on all reachable branches.

    Create the relationship on the default branch, fork a branch, delete a peer on the branch,
    verify the relationship is still active on the global branch, remove the relationship schema
    on the default branch, verify the agnostic relationship is closed.
    """
    gadget = await _create_gadget(db=db, branch=default_branch, name="peer-lost-on-the-fork")
    widget = await _create_widget(db=db, branch=default_branch, name="half-a-relationship", serial=1000, gadget=gadget)
    branch = await create_branch(db=db, branch_name="deleted-one-peer")

    # delete the peer on the branch
    await _delete(db=db, node_id=gadget.id, branch=branch, at=Timestamp())

    before = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
    assert [edge.edge_type for edge in open_edges(before)].count("IS_RELATED") == 2, (
        "the delete on the fork releases nothing: the default branch still reads both peers as live"
    )
    assert await relationship_peer_shape(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER) == (2, 2)

    on_branch = await NodeManager.get_one(db=db, id=widget.id, branch=branch)
    assert on_branch is not None, "the fork holds the owner, so the owner axis alone would retain the field"
    assert await on_branch.get_relationship("gadget").get_peer(db=db) is None, (
        "the fork declares the relationship and reads exactly one of its two peers as live"
    )

    # remove the relationship schema on the default branch
    # now the branch-agnostic relationship is completely unreachable
    removed_at = Timestamp()
    result = await _remove_relationship_from_schema(db=db, branch=default_branch, at=removed_at)
    assert not result.errors
    assert result.nbr_migrations_executed == 1

    after = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
    assert_relationship_retired_at(after=after, before=before, at=removed_at)


async def test_an_attribute_removed_on_a_fork_is_closed_when_the_object_is_deleted_elsewhere(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """The fork keeps the object but no longer declares the attribute, so the delete releases the value.

    The one branch that still reads the object as live is the one the attribute was removed from, and
    the branch the object is deleted on is the one that declared it. Neither branch holds both axes, so
    nothing retains the value.
    """
    widget = await _create_widget(db=db, branch=default_branch, name="serial-dropped-by-a-fork", serial=600)
    branch = await create_branch(db=db, branch_name="dropped-the-attribute")

    removal = await _remove_attribute_from_schema(db=db, branch=branch, at=Timestamp())
    assert not removal.errors
    assert removal.nbr_migrations_executed == 1

    before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}, (
        "the removal on the fork releases nothing: the default branch declares the attribute and holds the object"
    )

    deleted_at = Timestamp()
    await _delete(db=db, node_id=widget.id, branch=default_branch, at=deleted_at)

    after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert_attribute_retired_at(after=after, before=before, at=deleted_at)

    owning_edges = await attribute_owning_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert sorted((edge.branch, edge.status, edge.to_time or "") for edge in owning_edges) == sorted(
        [
            (GLOBAL_BRANCH_NAME, "active", deleted_at.to_string()),
            (default_branch.name, "deleted", ""),
            (branch.name, "deleted", ""),
        ]
    ), "one tombstone per branch is left as it was; only the global edge is closed"

    on_branch = await NodeManager.get_one(db=db, id=widget.id, branch=branch)
    assert on_branch is not None, "the fork keeps the object, which is why only its field was released"


async def test_an_attribute_removed_from_the_schema_is_closed_when_the_only_fork_deleted_the_object(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """The fork still declares the attribute but holds no object, so the removal releases the value.

    The inverse split of the case above: the branch the removal runs on is the one that keeps the
    object, and the fork that goes on declaring the attribute is the one left with nothing to read it
    from.
    """
    widget = await _create_widget(db=db, branch=default_branch, name="serial-outlived-by-a-fork", serial=700)
    branch = await create_branch(db=db, branch_name="deleted-the-object")

    deleted_at = Timestamp()
    await _delete(db=db, node_id=widget.id, branch=branch, at=deleted_at)

    before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}, (
        "the delete on the fork releases nothing: the default branch holds the object and declares the attribute"
    )

    removed_at = Timestamp()
    result = await _remove_attribute_from_schema(db=db, branch=default_branch, at=removed_at)
    assert not result.errors
    assert result.nbr_migrations_executed == 1

    after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert_attribute_retired_at(after=after, before=before, at=removed_at)

    owning_edges = await attribute_owning_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert sorted((edge.branch, edge.status, edge.to_time or "") for edge in owning_edges) == sorted(
        [
            (GLOBAL_BRANCH_NAME, "active", removed_at.to_string()),
            (default_branch.name, "deleted", ""),
            (branch.name, "deleted", ""),
        ]
    ), "one tombstone per branch is left as it was; only the global edge is closed"

    on_default = await NodeManager.get_one(db=db, id=widget.id, branch=default_branch)
    assert on_default is not None, (
        "the object outlives its field on the branch the removal ran on, and the fork that still "
        "declares the field has no object to read it from"
    )


async def test_an_attribute_of_a_branch_agnostic_kind_is_closed_when_no_branch_declares_it(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """The owner is itself branch-agnostic, so its existence edge reads live on every branch.

    Retention then rests entirely on the field axis: no branch declares the attribute after the
    removal, so the value has no reader even though the object it belongs to is still very much alive.
    """
    beacon = await _create_beacon(db=db, branch=default_branch, name="loses-its-serial", serial=900)

    before = await attribute_global_edges(db=db, node_id=beacon.id, attribute_name=ATTRIBUTE_NAME)
    assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

    removed_at = Timestamp()
    result = await _remove_attribute_from_schema(
        db=db, branch=default_branch, at=removed_at, kind=BEACON_KIND, attribute_name=ATTRIBUTE_NAME
    )
    assert not result.errors
    assert result.nbr_migrations_executed == 1

    after = await attribute_global_edges(db=db, node_id=beacon.id, attribute_name=ATTRIBUTE_NAME)
    assert_attribute_retired_at(after=after, before=before, at=removed_at)


async def test_an_attribute_of_a_branch_agnostic_kind_stays_open_for_a_branch_that_forked_before(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """Agnostic attribute of agnostic object is not deleted while still accessible.

    The fork still declares the attribute, so the value keeps a reader and the removal releases
    nothing -- the same answer as for a branch-aware owner, reached through a different existence axis.
    """
    beacon = await _create_beacon(db=db, branch=default_branch, name="keeps-its-serial", serial=901)

    branch2 = await create_branch(branch_name="beacon-fork", db=db)
    registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=branch2.name)

    before = await attribute_global_edges(db=db, node_id=beacon.id, attribute_name=ATTRIBUTE_NAME)
    assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}

    removed_at = Timestamp()
    result = await _remove_attribute_from_schema(
        db=db, branch=default_branch, at=removed_at, kind=BEACON_KIND, attribute_name=ATTRIBUTE_NAME
    )
    assert not result.errors

    after = await attribute_global_edges(db=db, node_id=beacon.id, attribute_name=ATTRIBUTE_NAME)
    assert edge_summary(after) == edge_summary(before), "the fork still declares the attribute, so nothing is released"


async def test_removing_an_attribute_stamps_the_removal_time_on_its_vertex(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """The removal is a write, so it leaves its audit stamps on the field it closed.

    The attribute is branch-agnostic on a branch-aware object, so the edges carrying its value are on
    the global branch while the migration runs on the default branch -- and the default branch is one
    of the two whose writes maintain vertex metadata.
    """
    widget = await _create_widget(db=db, branch=default_branch, name="stamped-on-removal", serial=1000)

    before = await attribute_metadata(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert before.updated_at is not None, "precondition: creating the object stamped the attribute"

    removed_at = Timestamp()
    result = await _remove_attribute_from_schema(db=db, branch=default_branch, at=removed_at)
    assert not result.errors

    after = await attribute_metadata(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert after.updated_at == removed_at.to_string(), "the attribute vertex carries the removal time"
    assert after.updated_by == SYSTEM_USER_ID
    assert after.previous_updated_at == before.updated_at, "the pre-removal stamp is kept for a rollback"
    assert after.previous_updated_by == before.updated_by

    owner = await get_node_metadata(db=db, node_uuid=widget.id)
    assert owner["updated_at"] == removed_at.to_string(), "the owning node is stamped by the same write"


async def test_removing_a_relationship_stamps_the_removal_time_on_its_vertex(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """Same for a branch-agnostic relationship, whose vertex sits between two branch-aware objects.

    The removal touches both peers, so both peer nodes carry its stamp, each snapshotting its own
    pre-removal values.
    """
    gadget = await _create_gadget(db=db, branch=default_branch, name="peer-of-the-stamped")
    widget = await _create_widget(
        db=db, branch=default_branch, name="stamped-on-rel-removal", serial=1001, gadget=gadget
    )

    before = await relationship_metadata(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
    assert before.updated_at is not None, "precondition: creating the relationship stamped its vertex"
    before_peers = {node.id: await get_node_metadata(db=db, node_uuid=node.id) for node in (widget, gadget)}

    removed_at = Timestamp()
    result = await _remove_relationship_from_schema(db=db, branch=default_branch, at=removed_at)
    assert not result.errors

    after = await relationship_metadata(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
    assert after.updated_at == removed_at.to_string(), "the relationship vertex carries the removal time"
    assert after.updated_by == SYSTEM_USER_ID
    assert after.previous_updated_at == before.updated_at, "the pre-removal stamp is kept for a rollback"
    assert after.previous_updated_by == before.updated_by

    for node in (widget, gadget):
        peer_meta = await get_node_metadata(db=db, node_uuid=node.id)
        assert peer_meta["updated_at"] == removed_at.to_string(), "both peer nodes are stamped by the same write"
        assert peer_meta["previous_updated_at"] == before_peers[node.id]["updated_at"], (
            "each peer keeps its own pre-removal stamp for a rollback"
        )


async def test_a_rolled_back_removal_leaves_the_global_edges_open(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """A schema update that fails after the removal committed must undo global branch changes.

    The edges reopen, and the stamps the removal wrote on the vertices it touched are restored
    from their snapshots, which the restore consumes.
    """
    widget = await _create_widget(db=db, branch=default_branch, name="keeps-its-serial", serial=300)

    before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert open_edge_types(before) == {"HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED"}
    before_meta = await attribute_metadata(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    before_owner = await get_node_metadata(db=db, node_uuid=widget.id)

    removed_at = Timestamp()
    result = await _remove_attribute_from_schema(db=db, branch=default_branch, at=removed_at)
    assert not result.errors
    closed = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert open_edges(closed) == [], "precondition: the removal closed the global edges"

    await GraphRollbacker(db=db).rollback(
        target_branch=default_branch,
        at=removed_at,
        scope=RollbackScope.AT_TIMESTAMP,
    )

    after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert edge_summary(after) == edge_summary(before), "every global edge is back to the state the removal found"

    after_meta = await attribute_metadata(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert after_meta == VertexMetadata(
        updated_at=before_meta.updated_at,
        updated_by=before_meta.updated_by,
        previous_updated_at=None,
        previous_updated_by=None,
    ), "the attribute vertex carries its pre-removal stamps again"

    after_owner = await get_node_metadata(db=db, node_uuid=widget.id)
    assert after_owner["updated_at"] == before_owner["updated_at"], "the owning node is restored by the same pass"
    assert after_owner["previous_updated_at"] is None

    owning_edges = await attribute_owning_edges(db=db, node_id=widget.id, attribute_name=ATTRIBUTE_NAME)
    assert sorted((edge.branch, edge.status, edge.to_time or "") for edge in owning_edges) == [
        (GLOBAL_BRANCH_NAME, "active", ""),
    ], "the removal's branch-scoped tombstone is gone and the global owning edge is open again"
