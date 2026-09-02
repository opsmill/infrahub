"""The repair migration must not release a value a branch can still read.

An object deleted on the default branch is still readable from every branch that forked before the
deletion, and its branch-agnostic values go on belonging to it there. The migration's candidate set is
every branch-agnostic field in the graph and its stamp is derivable for exactly this shape, so
retention is the only thing standing between a legitimately-readable value and an irreversible close.
Once no branch holds the object any more, the same candidate is released on the next run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.initialization import create_branch
from infrahub.core.timestamp import Timestamp
from tests.component.core.migrations.graph.m078_retire_agnostic_property_edges.conftest import (
    run_migration,
)
from tests.helpers.agnostic_edges import (
    attribute_global_edges,
    create_gadget,
    create_widget,
    edge_summary,
    open_edges,
    relationship_global_edges,
    to_times,
    tombstone_existence_only,
)
from tests.helpers.schema.agnostic_retirement import RELATIONSHIP_IDENTIFIER

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def test_a_branch_forked_before_the_deletion_keeps_the_value_reserved(
    db: InfrahubDatabase, default_branch: Branch, agnostic_schema: None
) -> None:
    """The branch still reads the object, so its attribute and its relationship are left untouched.

    Both are covered in one run because the retention rule is the same predicate for either: the
    attribute needs one live owner and the relationship needs two live peers, and the forked branch
    supplies the widget for both.
    """
    created_at = Timestamp().subtract(seconds=1800)
    gadget = await create_gadget(db=db, branch=default_branch, name="peer-of-the-retained-widget", at=created_at)
    widget = await create_widget(
        db=db, branch=default_branch, name="retained-by-a-branch", serial=9701, at=created_at, gadget=gadget
    )

    attribute_before = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
    relationship_before = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
    assert open_edges(attribute_before), "the fixture has to start with the value reserved"

    branch = await create_branch(db=db, branch_name="forked-before-the-deletion")
    gone_at = Timestamp()
    await tombstone_existence_only(db=db, node_id=widget.id, branch=default_branch, at=gone_at)

    retaining_run = await run_migration(db=db)
    assert not retaining_run.result.errors
    assert retaining_run.result.nbr_migrations_executed == 0
    assert "Closed 0 branch-agnostic edge(s)" in retaining_run.output

    assert edge_summary(await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")) == (
        edge_summary(attribute_before)
    ), "the forked branch still reads the widget, so its serial must stay exactly as it was"
    assert edge_summary(
        await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
    ) == edge_summary(relationship_before), "the forked branch reads both peers live, so the relationship stays open"

    branch.status = BranchStatus.DELETING
    await branch.save(db=db)

    released_run = await run_migration(db=db)
    assert not released_run.result.errors
    assert released_run.result.nbr_migrations_executed > 0

    attribute_after = await attribute_global_edges(db=db, node_id=widget.id, attribute_name="serial")
    relationship_after = await relationship_global_edges(db=db, node_id=widget.id, identifier=RELATIONSHIP_IDENTIFIER)
    assert open_edges(attribute_after) == []
    assert open_edges(relationship_after) == []
    assert to_times(attribute_after) == {gone_at.to_string()}
    assert to_times(relationship_after) == {gone_at.to_string()}
