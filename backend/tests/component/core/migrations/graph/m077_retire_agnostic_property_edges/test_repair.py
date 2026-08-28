"""Every damaged shape the repair migration handles, in one graph, repaired in one run.

The shapes are built together rather than one per test because that is how a real upgrade meets
them: a single pass over a graph holding all of them at once, where a candidate bound too widely
would take a neighbouring shape with it. The run happens once, the whole graph is verified, the run
happens again, and the same verification has to hold -- which is what makes the second pass a
statement about idempotency rather than a separate scenario.

Shapes are keyed by field-vertex uuid rather than by owner, because a kind change leaves two node
vertices on one uuid and a reader that starts from the owner would see that vertex's edges twice.

Retention lives in its own module: it needs a branch, and a branch forked into this graph would read
every object here that is still live, leaving the migration nothing to repair.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.timestamp import Timestamp
from tests.component.core.migrations.graph.m077_retire_agnostic_property_edges.conftest import (
    MigrationRun,
    attribute_value_count,
    close_global_owning_edge,
    close_global_property_edges,
    close_one_relationship_arm,
    detach_node_vertices,
    detached_field_uuids,
    duplicate_node_vertex,
    field_vertex_exists,
    remove_existence_edges,
    run_migration,
    value_vertex_ids,
)
from tests.helpers.agnostic_edges import (
    EdgeState,
    attribute_vertex_uuid,
    create_gadget,
    create_widget,
    edge_summary,
    expected_closed_at,
    global_edges_by_vertex_uuid,
    inverted_edges,
    node_vertex_count,
    open_active_edges,
    relationship_vertex_uuid,
    to_times,
    tombstone_existence_only,
    values_reachable_over_open_edges,
)
from tests.helpers.schema.agnostic_retirement import AGNOSTIC_RETIREMENT_SCHEMA

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

SHARED_SERIAL = 8500
"""One serial on two widgets, so de-duplication points both attributes at a single value vertex."""


@dataclass(frozen=True)
class FieldVertex:
    """One `:Attribute` or `:Relationship` vertex and the global edges it carried before the run."""

    name: str
    uuid: str
    before: list[EdgeState]

    closes_at: Timestamp | None
    """When every open edge must end, or `None` where the edges close at times of their own."""


@dataclass(frozen=True)
class DamagedGraph:
    repaired: list[FieldVertex]
    """Field vertices the run must close, each damaged in a different way."""

    untouched: list[FieldVertex]
    """Field vertices a readable object still holds, which the run must leave exactly as they are."""

    unstampable: FieldVertex
    """Nothing in the graph dates this one's release, so only the run's own time is left to close it."""

    survivor_node_id: str
    shared_value_ids: set[str]
    detached_uuids: set[str]
    value_count_before: int
    expected_closures: int


class TestRepairMigration:
    @pytest.fixture(scope="class")
    async def agnostic_schema(self, db: InfrahubDatabase, default_branch_scope_class: Branch) -> None:
        registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch_scope_class.name)

    @pytest.fixture(scope="class")
    async def graph(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, agnostic_schema: None
    ) -> DamagedGraph:
        branch = default_branch_scope_class
        created_at = Timestamp().subtract(seconds=1800)
        gone_at = Timestamp().subtract(seconds=600)
        repaired: list[FieldVertex] = []
        untouched: list[FieldVertex] = []

        # TODO: can this be a regular method on the class?
        async def snapshot(name: str, uuid: str, closes_at: Timestamp | None) -> FieldVertex:
            return FieldVertex(
                name=name,
                uuid=uuid,
                before=await global_edges_by_vertex_uuid(db=db, vertex_uuid=uuid),
                closes_at=closes_at,
            )

        # A tombstoned object whose field edges the deletion never touched, attribute and peer alike.
        peer = await create_gadget(db=db, branch=branch, name="orphan-peer", at=created_at)
        orphan = await create_widget(db=db, branch=branch, name="orphan", serial=8001, at=created_at, gadget=peer)
        await tombstone_existence_only(db=db, node_id=orphan.id, branch=branch, at=gone_at)
        repaired.extend(
            [
                await snapshot(
                    "orphan attribute", attribute_vertex_uuid(node=orphan, attribute_name="serial"), gone_at
                ),
                await snapshot(
                    "orphan relationship", relationship_vertex_uuid(node=orphan, relationship_name="gadget"), gone_at
                ),
            ]
        )

        # A second orphan that went away later, so one run cannot use a single stamp for both.
        later_gone_at = Timestamp().subtract(seconds=300)
        later = await create_widget(db=db, branch=branch, name="later-orphan", serial=8002, at=created_at)
        await tombstone_existence_only(db=db, node_id=later.id, branch=branch, at=later_gone_at)
        repaired.append(
            await snapshot("later orphan", attribute_vertex_uuid(node=later, attribute_name="serial"), later_gone_at)
        )

        # A value written after the owner went away: its edge begins later than the derived stamp, so it
        # closes at its own start rather than being given an interval that ends before it begins.
        late_edge = await create_widget(
            db=db, branch=branch, name="updated-after-its-owner-went", serial=8003, at=created_at
        )
        late_edge.get_attribute(name="serial").value = 8004
        await late_edge.save(db=db, at=Timestamp().subtract(seconds=120))
        await tombstone_existence_only(db=db, node_id=late_edge.id, branch=branch, at=gone_at)
        repaired.append(
            await snapshot(
                "value written after its owner went",
                attribute_vertex_uuid(node=late_edge, attribute_name="serial"),
                None,
            )
        )

        # The reported damage: the owning edge shut while the value edge stayed open.
        half_closed_owner = await create_widget(
            db=db, branch=branch, name="half-closed-owner", serial=8005, at=created_at
        )
        half_closed_owner_uuid = attribute_vertex_uuid(node=half_closed_owner, attribute_name="serial")
        await tombstone_existence_only(db=db, node_id=half_closed_owner.id, branch=branch, at=gone_at)
        await close_global_owning_edge(db=db, field_uuid=half_closed_owner_uuid, at=gone_at)
        repaired.append(await snapshot("owning edge already shut", half_closed_owner_uuid, gone_at))

        # The mirror shape: the property edges shut while the owning edge stayed open.
        half_closed_value = await create_widget(
            db=db, branch=branch, name="half-closed-value", serial=8006, at=created_at
        )
        half_closed_value_uuid = attribute_vertex_uuid(node=half_closed_value, attribute_name="serial")
        await tombstone_existence_only(db=db, node_id=half_closed_value.id, branch=branch, at=gone_at)
        await close_global_property_edges(db=db, field_uuid=half_closed_value_uuid, at=gone_at)
        repaired.append(await snapshot("property edges already shut", half_closed_value_uuid, gone_at))

        # A relationship reaching one peer is not a relationship, though both its owners are live.
        one_armed_peer = await create_gadget(db=db, branch=branch, name="one-armed-peer", at=created_at)
        one_armed = await create_widget(
            db=db, branch=branch, name="one-armed-owner", serial=8007, at=created_at, gadget=one_armed_peer
        )
        one_armed_uuid = relationship_vertex_uuid(node=one_armed, relationship_name="gadget")
        arm_closed_at = Timestamp().subtract(seconds=500)
        await close_one_relationship_arm(db=db, field_uuid=one_armed_uuid, peer_id=one_armed_peer.id, at=arm_closed_at)
        repaired.append(await snapshot("relationship left with one arm", one_armed_uuid, arm_closed_at))
        untouched.append(
            await snapshot(
                "one-armed owner keeps its own attribute",
                attribute_vertex_uuid(node=one_armed, attribute_name="serial"),
                None,
            )
        )

        # Removing the field from the schema stranded the value while the owner lived on.
        schema_removed = await create_widget(
            db=db, branch=branch, name="schema-removed-field", serial=8008, at=created_at
        )
        schema_removed_uuid = attribute_vertex_uuid(node=schema_removed, attribute_name="serial")
        removed_at = Timestamp().subtract(seconds=400)
        await close_global_owning_edge(db=db, field_uuid=schema_removed_uuid, at=removed_at)
        repaired.append(await snapshot("field removed from the schema", schema_removed_uuid, removed_at))

        # A kind change leaves a stale same-uuid vertex whose older edge must not date the release.
        duplicated = await create_widget(db=db, branch=branch, name="kind-migrated-widget", serial=8009, at=created_at)
        duplicated_uuid = attribute_vertex_uuid(node=duplicated, attribute_name="serial")
        await duplicate_node_vertex(db=db, node_id=duplicated.id, at=Timestamp().subtract(seconds=1200))
        assert await node_vertex_count(db=db, node_id=duplicated.id) == 2, (
            "the fixture needs two node vertices on one uuid, or there is no stale candidate"
        )
        released_at = Timestamp().subtract(seconds=200)
        await close_global_owning_edge(db=db, field_uuid=duplicated_uuid, at=released_at)
        repaired.append(await snapshot("owner superseded by a kind change", duplicated_uuid, released_at))

        # Two widgets on one value vertex, one orphaned: the survivor must go on reading it.
        shared_orphan = await create_widget(
            db=db, branch=branch, name="shared-value-orphan", serial=SHARED_SERIAL, at=created_at
        )
        survivor = await create_widget(
            db=db, branch=branch, name="shared-value-survivor", serial=SHARED_SERIAL, at=created_at
        )
        shared_value_ids = await value_vertex_ids(db=db, node_id=shared_orphan.id, attribute_name="serial")
        assert len(shared_value_ids) == 1
        assert shared_value_ids == await value_vertex_ids(db=db, node_id=survivor.id, attribute_name="serial"), (
            "the fixture depends on de-duplication pointing both attributes at one value vertex"
        )
        shared_orphan_uuid = attribute_vertex_uuid(node=shared_orphan, attribute_name="serial")
        survivor_uuid = attribute_vertex_uuid(node=survivor, attribute_name="serial")
        assert shared_orphan_uuid != survivor_uuid, "de-duplication is on the value vertex, not the attribute vertex"
        await tombstone_existence_only(db=db, node_id=shared_orphan.id, branch=branch, at=gone_at)
        repaired.append(await snapshot("orphaned sharer of a value vertex", shared_orphan_uuid, gone_at))
        untouched.append(await snapshot("surviving sharer of a value vertex", survivor_uuid, None))

        # An object whose live neighbour proves the candidate bound is not simply "every field".
        live_peer = await create_gadget(db=db, branch=branch, name="live-peer", at=created_at)
        live = await create_widget(
            db=db, branch=branch, name="still-readable", serial=8011, at=created_at, gadget=live_peer
        )
        untouched.extend(
            [
                await snapshot("readable attribute", attribute_vertex_uuid(node=live, attribute_name="serial"), None),
                await snapshot(
                    "readable relationship", relationship_vertex_uuid(node=live, relationship_name="gadget"), None
                ),
            ]
        )

        # A field nothing in the graph can date, so only the run's own time is left to close it with.
        unstampable_widget = await create_widget(
            db=db, branch=branch, name="no-stamp-derivable", serial=8010, at=created_at
        )
        unstampable_uuid = attribute_vertex_uuid(node=unstampable_widget, attribute_name="serial")
        await remove_existence_edges(db=db, node_id=unstampable_widget.id)
        unstampable = await snapshot("no derivable stamp", unstampable_uuid, None)

        # Field vertices whose node vertices are gone outright, which are removed rather than closed.
        detached_peer = await create_gadget(db=db, branch=branch, name="detached-peer", at=created_at)
        detached_owner = await create_widget(
            db=db, branch=branch, name="detached-owner", serial=8012, at=created_at, gadget=detached_peer
        )
        agnostic_detached = {
            attribute_vertex_uuid(node=detached_owner, attribute_name="serial"),
            relationship_vertex_uuid(node=detached_owner, relationship_name="gadget"),
        }
        await detach_node_vertices(db=db, node_ids=[detached_owner.id, detached_peer.id])
        # Removing a node vertex strands every field it owned, the branch-aware ones included, and the
        # hard delete takes all of them; the agnostic pair is the subset this feature is about.
        detached_uuids = await detached_field_uuids(db=db)
        assert agnostic_detached <= detached_uuids, "the fixture needs the agnostic field vertices detached"

        return DamagedGraph(
            repaired=repaired,
            untouched=untouched,
            unstampable=unstampable,
            survivor_node_id=survivor.id,
            shared_value_ids=shared_value_ids,
            detached_uuids=detached_uuids,
            value_count_before=await attribute_value_count(db=db),
            expected_closures=sum(len(open_active_edges(shape.before)) for shape in [*repaired, unstampable]),
        )

    @pytest.fixture(scope="class")
    async def first_run(self, db: InfrahubDatabase, graph: DamagedGraph) -> MigrationRun:
        return await run_migration(db=db)

    @pytest.fixture(scope="class")
    async def second_run(self, db: InfrahubDatabase, first_run: MigrationRun) -> MigrationRun:
        return await run_migration(db=db)

    async def verify_migration(self, db: InfrahubDatabase, graph: DamagedGraph, run_at: Timestamp) -> None:
        """The state every shape must be in once the migration has run, whichever run produced it."""
        for shape in [*graph.repaired, graph.unstampable]:
            after = await global_edges_by_vertex_uuid(db=db, vertex_uuid=shape.uuid)
            assert open_active_edges(after) == [], f"{shape.name}: the value is still reserved"
            # A tombstone is not a reachable value, so the close passes over it and leaves it open.
            assert edge_summary([edge for edge in after if not edge.is_active]) == edge_summary(
                [edge for edge in shape.before if not edge.is_active]
            ), f"{shape.name}: an inactive edge must come through the run untouched"
            if shape.closes_at is not None:
                assert edge_summary([edge for edge in after if edge.is_active]) == expected_closed_at(
                    [edge for edge in shape.before if edge.is_active], shape.closes_at
                ), f"{shape.name}: the close does not carry the time the field stopped being reachable"

        unstampable_after = await global_edges_by_vertex_uuid(db=db, vertex_uuid=graph.unstampable.uuid)
        assert to_times([edge for edge in unstampable_after if edge.is_active]) == {run_at.to_string()}, (
            "with nothing in the graph to date the release, the close carries the first run's own time"
        )

        for shape in graph.untouched:
            after = await global_edges_by_vertex_uuid(db=db, vertex_uuid=shape.uuid)
            assert edge_summary(after) == edge_summary(shape.before), (
                f"{shape.name}: a readable field must survive the run exactly as it was"
            )

        assert (
            await value_vertex_ids(db=db, node_id=graph.survivor_node_id, attribute_name="serial")
            == graph.shared_value_ids
        )
        assert await values_reachable_over_open_edges(
            db=db, node_id=graph.survivor_node_id, attribute_name="serial"
        ) == [SHARED_SERIAL], "the survivor goes on reading the value vertex its orphaned twin shared with it"

        for vertex_uuid in graph.detached_uuids:
            assert not await field_vertex_exists(db=db, vertex_uuid=vertex_uuid)

    async def verify_graph(self, db: InfrahubDatabase, graph: DamagedGraph) -> None:
        """Invariants over the whole graph rather than over any one shape."""
        assert await detached_field_uuids(db=db) == set(), "no field vertex may be left without a node vertex"
        assert await attribute_value_count(db=db) == graph.value_count_before, (
            "value vertices are shared, so neither a close nor a hard delete may take one with it"
        )
        for shape in [*graph.repaired, *graph.untouched, graph.unstampable]:
            after = await global_edges_by_vertex_uuid(db=db, vertex_uuid=shape.uuid)
            assert inverted_edges(after) == [], f"{shape.name}: no edge may be left ending before it begins"

    async def test_the_first_run_repairs_every_damaged_shape(
        self, db: InfrahubDatabase, graph: DamagedGraph, first_run: MigrationRun
    ) -> None:
        assert not first_run.result.errors
        await self.verify_migration(db=db, graph=graph, run_at=first_run.at)

    async def test_the_first_run_reports_what_it_changed(self, graph: DamagedGraph, first_run: MigrationRun) -> None:
        """One count over every shape at once, which no per-shape assertion can check."""
        assert f"Closed {graph.expected_closures} branch-agnostic edge(s)" in first_run.output
        assert f"Removed {len(graph.detached_uuids)} attribute or relationship vertex" in first_run.output
        assert first_run.result.nbr_migrations_executed == graph.expected_closures + len(graph.detached_uuids)

    async def test_a_second_run_leaves_the_repaired_graph_alone(
        self, db: InfrahubDatabase, graph: DamagedGraph, first_run: MigrationRun, second_run: MigrationRun
    ) -> None:
        """An interrupted upgrade is resumed by running it again, so a repeat pass must change nothing."""
        assert not second_run.result.errors
        assert second_run.result.nbr_migrations_executed == 0
        assert "Closed 0 branch-agnostic edge(s)" in second_run.output
        assert "Removed 0 attribute or relationship vertex" in second_run.output
        await self.verify_migration(db=db, graph=graph, run_at=first_run.at)

    async def test_the_repaired_graph_holds_no_damage(
        self, db: InfrahubDatabase, graph: DamagedGraph, second_run: MigrationRun
    ) -> None:
        await self.verify_graph(db=db, graph=graph)
