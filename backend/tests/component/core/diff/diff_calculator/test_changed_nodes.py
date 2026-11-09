"""The changed-nodes queries list only nodes the field- and property-level paths queries can return paths for."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.query.diff import DiffChangedNodesQuery, DiffFieldNodesQuery, DiffPropertyNodesQuery
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

LOCAL_NOTE_KIND = "TestingLocalNote"


@pytest.fixture
async def local_note_schema(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> None:
    """A branch-local kind, whose changes on a branch never enter a diff."""
    local_note = NodeSchema(
        name="LocalNote",
        namespace="Testing",
        branch=BranchSupportType.LOCAL,
        default_filter="name__value",
        attributes=[
            AttributeSchema(name="name", kind="Text", unique=True),
            AttributeSchema(name="text", kind="Text", optional=True),
        ],
    )
    registry.schema.register_schema(schema=SchemaRoot(nodes=[local_note]), branch=default_branch.name)


async def _changed_node_uuids(
    db: InfrahubDatabase, query_class: type[DiffChangedNodesQuery], base_branch: Branch, branch: Branch
) -> list[str]:
    query = await query_class.init(
        db=db,
        branch=branch,
        base_branch=base_branch,
        diff_branch_from_time=Timestamp(branch.created_at),
        diff_from=Timestamp(branch.created_at),
        diff_to=Timestamp(),
    )
    await query.execute(db=db)
    return query.get_node_uuids()


@pytest.mark.parametrize("query_class", [DiffFieldNodesQuery, DiffPropertyNodesQuery])
async def test_branch_local_changes_are_not_listed(
    db: InfrahubDatabase,
    default_branch: Branch,
    local_note_schema: None,
    query_class: type[DiffChangedNodesQuery],
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    note = await Node.init(db=db, schema=LOCAL_NOTE_KIND, branch=branch)
    await note.new(db=db, name="note-1", text="branch only")
    await note.save(db=db)

    assert await _changed_node_uuids(db=db, query_class=query_class, base_branch=default_branch, branch=branch) == []


@pytest.mark.parametrize("query_class", [DiffFieldNodesQuery, DiffPropertyNodesQuery])
async def test_branch_aware_changes_are_listed(
    db: InfrahubDatabase,
    default_branch: Branch,
    local_note_schema: None,
    query_class: type[DiffChangedNodesQuery],
) -> None:
    branch = await create_branch(db=db, branch_name="branch")
    note = await Node.init(db=db, schema=LOCAL_NOTE_KIND, branch=branch)
    await note.new(db=db, name="note-1", text="branch only")
    await note.save(db=db)
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name="Alice", height=170)
    await person.save(db=db)

    assert await _changed_node_uuids(db=db, query_class=query_class, base_branch=default_branch, branch=branch) == [
        person.id
    ]
