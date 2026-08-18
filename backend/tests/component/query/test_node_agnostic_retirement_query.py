"""Graph-shape assertions for the retirement of one node's branch-agnostic fields.

Every assertion reads the edges directly rather than going through the node manager: the subject is
which edges carry a `to` timestamp and which do not, and a read through the manager would hide the
very states these tests exist to pin down.
"""

from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    SchemaPathType,
)
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import (
    NodeKindUpdateMigration,
    NodeKindUpdateMigrationQuery01,
)
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.query.node_agnostic_retirement import (
    NodeAgnosticRetirementResult,
    RetireNodeAgnosticFieldsQuery,
)
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.agnostic_edges import (
    attribute_global_edges,
    attribute_vertex_count,
    edge_summary,
    node_vertex_count,
    open_active_edges,
    open_edges,
    relationship_global_edges,
    relationship_peer_shape,
    tombstone_existence_only,
    tombstone_relationship_peer_edge,
    values_reachable_over_open_edges,
)
from tests.helpers.schema.agnostic_retirement import (
    AGNOSTIC_RETIREMENT_SCHEMA,
    BEACON_KIND,
    GADGET_KIND,
    RELATIONSHIP_IDENTIFIER,
    WIDGET_KIND,
)


async def _rename_widget_kind(db: InfrahubDatabase, branch: Branch) -> None:
    """Rename the widget kind in the graph, leaving a superseded node vertex under the same uuid.

    The copy shares the original's attribute and relationship vertices, so a field vertex is linked to
    both the live copy and the superseded one.
    """
    previous_schema = registry.schema.get_node_schema(name=WIDGET_KIND, branch=branch, duplicate=False)
    renamed_schema = registry.schema.get_node_schema(name=WIDGET_KIND, branch=branch, duplicate=True)
    renamed_schema.name = "RenamedWidget"

    migration = NodeKindUpdateMigration(
        previous_node_schema=previous_schema,
        new_node_schema=renamed_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=renamed_schema.kind, field_name="name"),
    )
    query = await NodeKindUpdateMigrationQuery01.init(db=db, branch=branch, migration=migration)
    await query.execute(db=db)


async def _retire(db: InfrahubDatabase, node_id: str, at: Timestamp) -> NodeAgnosticRetirementResult:
    query = await RetireNodeAgnosticFieldsQuery.init(db=db, node_uuid=node_id, at=at)
    await query.execute(db=db)
    return query.get_data()


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


class TestRetireNodeAgnosticFields:
    @pytest.fixture(scope="class")
    async def default_branch(self, default_branch_scope_class: Branch) -> Branch:
        return default_branch_scope_class

    @pytest.fixture(scope="class")
    async def nodedel_schema(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        registry.schema.register_schema(schema=AGNOSTIC_RETIREMENT_SCHEMA, branch=default_branch.name)

    async def test_an_anchor_that_matches_nothing_reports_a_measured_zero(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        nodedel_schema: None,
    ) -> None:
        """Ensure the query returns 0 when it does nothing, and that the anchor is what limited it.

        A retirable object is present and left alone, so the zero says "this uuid owns nothing" rather
        than "the database held nothing to find". The row itself matters too: the query ends in an
        aggregation with no grouping key, and a missing row would leave the outcome unknown.
        """
        bystander = await _create_widget(db=db, branch=default_branch, name="not-the-anchor", serial=1000)
        await tombstone_existence_only(db=db, node_id=bystander.get_id(), branch=default_branch, at=Timestamp())
        bystander_before = await attribute_global_edges(db=db, node_id=bystander.get_id(), attribute_name="serial")
        assert open_active_edges(bystander_before) != [], (
            "the bystander has to be retirable, or the anchor is not what spared it"
        )

        query = await RetireNodeAgnosticFieldsQuery.init(db=db, node_uuid="no-node-carries-this-uuid", at=Timestamp())
        await query.execute(db=db)

        assert query.get_result() is not None
        assert query.get_data() == NodeAgnosticRetirementResult(edges_closed=0)
        assert edge_summary(
            await attribute_global_edges(db=db, node_id=bystander.get_id(), attribute_name="serial")
        ) == edge_summary(bystander_before), "the unrelated retirable object is untouched"

    async def test_branch_agnostic_object_is_not_deleted_while_active(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        nodedel_schema: None,
    ) -> None:
        """Verify branch-agnostic object is not improperly deleted by the retirement query."""
        beacon = await Node.init(db=db, schema=BEACON_KIND, branch=default_branch)
        await beacon.new(db=db, name="beacon-alive")
        await beacon.save(db=db)

        before = await attribute_global_edges(db=db, node_id=beacon.get_id(), attribute_name="name")
        assert open_edges(before) != []

        assert await _retire(db=db, node_id=beacon.get_id(), at=Timestamp()) == NodeAgnosticRetirementResult(
            edges_closed=0
        )
        assert edge_summary(
            await attribute_global_edges(db=db, node_id=beacon.get_id(), attribute_name="name")
        ) == edge_summary(before)

    async def test_an_owner_that_is_itself_branch_agnostic_is_closed_once_by_its_own_deletion(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        nodedel_schema: None,
    ) -> None:
        """Ensure deleting a branch-agnostic object leaves nothing for the retirement query to address."""
        beacon = await Node.init(db=db, schema=BEACON_KIND, branch=default_branch)
        await beacon.new(db=db, name="beacon-deleted")
        await beacon.save(db=db)
        beacon_id = beacon.get_id()

        before = await attribute_global_edges(db=db, node_id=beacon_id, attribute_name="name")
        open_before = open_edges(before)
        assert open_before != []

        deleted_at = Timestamp()
        to_delete = await NodeManager.get_one(db=db, id=beacon_id, branch=default_branch)
        await to_delete.delete(db=db, at=deleted_at)

        after = await attribute_global_edges(db=db, node_id=beacon_id, attribute_name="name")

        assert {(edge.edge_type, edge.status) for edge in open_edges(after)} == {
            ("HAS_ATTRIBUTE", "deleted"),
            ("HAS_VALUE", "deleted"),
            ("IS_PROTECTED", "deleted"),
        }
        assert {edge.to_time for edge in after if edge.status == "active"} == {deleted_at.to_string()}

        assert await _retire(db=db, node_id=beacon_id, at=Timestamp()) == NodeAgnosticRetirementResult(edges_closed=0)

    async def test_partially_deleted_object_is_retired(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        nodedel_schema: None,
    ) -> None:
        """Object with a closed IS_PART_OF edge and an active agnostic field is retired."""
        widget = await _create_widget(db=db, branch=default_branch, name="orphan-holder", serial=8100)
        before = await attribute_global_edges(db=db, node_id=widget.get_id(), attribute_name="serial")
        open_before = open_edges(before)
        assert open_before != []

        await tombstone_existence_only(db=db, node_id=widget.get_id(), branch=default_branch, at=Timestamp())

        unchanged = await attribute_global_edges(db=db, node_id=widget.get_id(), attribute_name="serial")
        assert edge_summary(unchanged) == edge_summary(before)

        retired_at = Timestamp()
        assert await _retire(db=db, node_id=widget.get_id(), at=retired_at) == NodeAgnosticRetirementResult(
            edges_closed=len(open_before)
        )

        after = await attribute_global_edges(db=db, node_id=widget.get_id(), attribute_name="serial")
        assert open_edges(after) == []
        assert {edge.to_time for edge in after if edge.status == "active"} == {retired_at.to_string()}

    async def test_a_relationship_stays_open_while_both_peers_are_live_on_one_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        nodedel_schema: None,
    ) -> None:
        gadget = await _create_gadget(db=db, branch=default_branch, name="live-peer")
        widget = await _create_widget(db=db, branch=default_branch, name="live-owner", serial=500, gadget=gadget)

        before = await relationship_global_edges(db=db, node_id=widget.get_id(), identifier=RELATIONSHIP_IDENTIFIER)
        assert [edge.edge_type for edge in open_edges(before)].count("IS_RELATED") == 2

        at = Timestamp()
        assert await _retire(db=db, node_id=widget.id, at=at) == NodeAgnosticRetirementResult(edges_closed=0)
        assert await _retire(db=db, node_id=gadget.id, at=at) == NodeAgnosticRetirementResult(edges_closed=0)

        assert edge_summary(
            await relationship_global_edges(db=db, node_id=widget.get_id(), identifier=RELATIONSHIP_IDENTIFIER)
        ) == (edge_summary(before))

    async def test_a_sourced_and_owned_attribute_closes_every_property_edge_type(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        nodedel_schema: None,
    ) -> None:
        """Verify HAS_OWNER and HAS_SOURCE edges are retired correctly."""
        source = await _create_gadget(db=db, branch=default_branch, name="the-source")
        owner = await _create_gadget(db=db, branch=default_branch, name="the-owner")

        widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
        await widget.new(
            db=db,
            name="sourced-and-owned",
            serial={"value": 2200, "source": source.get_id(), "owner": owner.get_id()},
        )
        await widget.save(db=db)

        before = await attribute_global_edges(db=db, node_id=widget.get_id(), attribute_name="serial")
        assert {edge.edge_type for edge in open_edges(before)} == {
            "HAS_ATTRIBUTE",
            "HAS_VALUE",
            "IS_PROTECTED",
            "HAS_SOURCE",
            "HAS_OWNER",
        }, "the attribute is expected to hold all four property edge types plus its owning edge"

        await tombstone_existence_only(db=db, node_id=widget.get_id(), branch=default_branch, at=Timestamp())

        at = Timestamp()
        assert await _retire(db=db, node_id=widget.get_id(), at=at) == NodeAgnosticRetirementResult(
            edges_closed=len(open_edges(before))
        )

        after = await attribute_global_edges(db=db, node_id=widget.get_id(), attribute_name="serial")
        assert open_edges(after) == []

    async def test_a_partially_closed_relationship_is_retired(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        nodedel_schema: None,
    ) -> None:
        """Verify an illegal Relationship with 1 closed IS_RELATED edge is correctly retired"""
        widget = await _create_widget(db=db, branch=default_branch, name="tombstoned-peer-edge", serial=2000)
        gadget = await _create_gadget(db=db, branch=default_branch, name="tombstoned-peer-edge-gadget")
        await widget.get_relationship(name="gadget").update(db=db, data=gadget)
        await widget.save(db=db)
        assert await relationship_peer_shape(db=db, node_id=widget.get_id(), identifier=RELATIONSHIP_IDENTIFIER) == (
            2,
            2,
        ), "the relationship is expected to reach two distinct live peers before one edge is tombstoned"

        await tombstone_relationship_peer_edge(
            db=db,
            node_id=widget.get_id(),
            identifier=RELATIONSHIP_IDENTIFIER,
            peer_id=gadget.get_id(),
            at=Timestamp(),
        )
        before = await relationship_global_edges(db=db, node_id=widget.get_id(), identifier=RELATIONSHIP_IDENTIFIER)
        assert edge_summary(before) == [
            ("IS_PROTECTED", "active", ""),
            ("IS_RELATED", "active", ""),
            ("IS_RELATED", "active", ""),
            ("IS_RELATED", "deleted", ""),
        ], "the tombstone is a new edge alongside the active one it supersedes, and both are open"
        attribute_before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")

        at = Timestamp()
        assert await _retire(db=db, node_id=widget.id, at=at) == NodeAgnosticRetirementResult(edges_closed=3)

        assert edge_summary(
            await relationship_global_edges(db=db, node_id=widget.get_id(), identifier=RELATIONSHIP_IDENTIFIER)
        ) == [
            ("IS_PROTECTED", "active", at.to_string()),
            ("IS_RELATED", "active", at.to_string()),
            ("IS_RELATED", "active", at.to_string()),
            ("IS_RELATED", "deleted", ""),
        ], "every active edge is closed and the tombstone is left exactly as it was"
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(attribute_before)
        ), "the live node's own attribute is retained, so only the relationship was released"

    async def test_relationship_with_renamed_peer_is_retired(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        nodedel_schema: None,
    ) -> None:
        """Relationship linked to a peer with an updated kind needs to still be retired correctly."""
        widget = await _create_widget(db=db, branch=default_branch, name="renamed-peer", serial=3300)
        gadget = await _create_gadget(db=db, branch=default_branch, name="renamed-peer-gadget")
        await widget.get_relationship(name="gadget").update(db=db, data=gadget)
        await widget.save(db=db)

        await _rename_widget_kind(db=db, branch=default_branch)
        assert await node_vertex_count(db=db, node_id=widget.id) == 2, (
            "the rename is expected to leave a superseded node vertex sharing the uuid"
        )

        await tombstone_existence_only(db=db, node_id=gadget.get_id(), branch=default_branch, at=Timestamp())

        before = await relationship_global_edges(db=db, node_id=widget.get_id(), identifier=RELATIONSHIP_IDENTIFIER)
        open_active_before = [edge for edge in open_edges(before) if edge.status == "active"]
        assert open_active_before != []
        attribute_before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")

        at = Timestamp()
        assert await _retire(db=db, node_id=widget.id, at=at) == NodeAgnosticRetirementResult(
            edges_closed=len(open_active_before)
        )

        after = await relationship_global_edges(db=db, node_id=widget.get_id(), identifier=RELATIONSHIP_IDENTIFIER)
        assert [edge for edge in open_edges(after) if edge.status == "active"] == [], (
            "every active edge of the relationship is closed once its second peer is gone"
        )
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(attribute_before)
        ), "the surviving `widget` still reads its own attribute, so only the relationship was released"

    async def test_a_renamed_kind_is_not_improperly_retired(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        nodedel_schema: None,
    ) -> None:
        """Verify a kind-migrated object is not improperly retired"""
        widget = await _create_widget(db=db, branch=default_branch, name="renamed-kind", serial=1100)

        await _rename_widget_kind(db=db, branch=default_branch)

        assert await node_vertex_count(db=db, node_id=widget.id) == 2, (
            "the rename is expected to leave a superseded node vertex sharing the uuid"
        )
        assert await attribute_vertex_count(db=db, node_id=widget.id, attribute_name="serial") == 1, (
            "both node vertices are expected to share one attribute vertex"
        )

        before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert await values_reachable_over_open_edges(db=db, node_id=widget.id, attribute_name="serial") == [1100]

        assert await _retire(db=db, node_id=widget.id, at=Timestamp()) == NodeAgnosticRetirementResult(edges_closed=0)

        assert await values_reachable_over_open_edges(db=db, node_id=widget.id, attribute_name="serial") == [1100]
        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(before)
        )

    async def test_a_second_run_over_an_already_retired_field_closes_nothing(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        nodedel_schema: None,
    ) -> None:
        """Verify that retirement is idempotent."""
        widget = await _create_widget(db=db, branch=default_branch, name="retired-once", serial=2500)

        deleted_at = Timestamp()
        to_delete = await NodeManager.get_one(db=db, id=widget.id, branch=default_branch, raise_on_error=True)
        await to_delete.delete(db=db, at=deleted_at)

        after_first_run = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
        assert edge_summary(after_first_run) == sorted(
            (edge_type, "active", deleted_at.to_string())
            for edge_type in ("HAS_ATTRIBUTE", "HAS_VALUE", "IS_PROTECTED")
        )

        second_run_at = Timestamp()
        assert second_run_at > deleted_at, "the second run's stamp is expected to be distinguishable from the first"

        assert await _retire(db=db, node_id=widget.id, at=second_run_at) == NodeAgnosticRetirementResult(edges_closed=0)

        assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
            edge_summary(after_first_run)
        )
