"""Merging when both branches changed the same schema property and the user chose a side.

Schema nodes are diffed like any other, so two edits to one property record a value conflict the merge
refuses until it is resolved. The merged schema then has to hold the side the user chose, and the
constraint check has to read that side too: the whole population is checked against the destination's
value when the destination wins, and against the source's when the source wins.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import lock
from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.model.path import BranchTrackingId, ConflictSelection, EnrichedDiffConflict
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import MergeConflictsUnresolvedError, MergeConstraintsViolatedError
from tests.helpers.merge import build_graph_merger, build_schema_analyzer, set_attribute_parameters
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.workflow.local import WorkflowLocalExecution

WIDGET_KIND = "TestingWidget"
PERMISSIVE = r".*"
UPPERCASE_ONLY = r"^[A-Z]+$"
LOWERCASE_ONLY = r"^[a-z]+$"


def _widget_schema() -> SchemaRoot:
    return SchemaRoot(
        nodes=[
            NodeSchema(
                name="Widget",
                namespace="Testing",
                default_filter="name__value",
                attributes=[
                    AttributeSchema(name="name", kind="Text"),
                    AttributeSchema(
                        name="code",
                        kind="Text",
                        optional=True,
                        parameters=TextAttributeParameters(regex=PERMISSIVE),
                    ),
                ],
            )
        ]
    )


def _code_regex(schema: SchemaBranch) -> str | None:
    parameters = schema.get(name=WIDGET_KIND).get_attribute(name="code").parameters
    assert isinstance(parameters, TextAttributeParameters)
    return parameters.regex


async def _fork_then_change_the_regex_on_both_sides(
    db: InfrahubDatabase, default_branch: Branch, branch_name: str, destination_code: str | None
) -> tuple[Node, Branch]:
    """One widget on the destination; the branch tightens the regex to uppercase, the destination to lowercase."""
    lock.initialize_lock(local_only=True)
    await load_schema(db=db, schema=_widget_schema(), update_db=True)
    widget = await Node.init(db=db, schema=WIDGET_KIND)
    await widget.new(db=db, name="widget-one", code=destination_code)
    await widget.save(db=db)

    branch = await create_branch(db=db, branch_name=branch_name)
    await set_attribute_parameters(
        db=db, branch=branch, node_kind=WIDGET_KIND, attribute_name="code", regex=UPPERCASE_ONLY
    )
    await set_attribute_parameters(
        db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", regex=LOWERCASE_ONLY
    )
    return widget, branch


async def _conflicts(db: InfrahubDatabase, default_branch: Branch, branch: Branch) -> dict[str, EnrichedDiffConflict]:
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    return {
        path: conflict
        async for path, conflict in diff_repository.get_all_conflicts_for_diff(
            diff_branch_name=branch.name, tracking_id=BranchTrackingId(name=branch.name)
        )
    }


async def _resolve_all(
    db: InfrahubDatabase, branch: Branch, conflicts: dict[str, EnrichedDiffConflict], selection: ConflictSelection
) -> None:
    diff_repository = await get_component_registry().get_component(DiffRepository, db=db, branch=branch)
    for conflict in conflicts.values():
        await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=selection)


def _code_schema_attribute_id(branch: Branch) -> str:
    attribute_id = registry.schema.get_node_schema(name=WIDGET_KIND, branch=branch).get_attribute(name="code").id
    assert attribute_id
    return attribute_id


async def test_the_regex_edited_on_both_sides_is_a_conflict_the_merge_refuses_unresolved(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_local: WorkflowLocalExecution,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Pins where the conflict lives.

    It sits on the ``parameters`` of the ``SchemaAttribute`` node and is mirrored on the deprecated
    top-level ``regex``, so a resolution has to cover both.
    """
    _, branch = await _fork_then_change_the_regex_on_both_sides(
        db=db, default_branch=default_branch, branch_name="regex-conflict-unresolved", destination_code=None
    )

    conflicts = await _conflicts(db=db, default_branch=default_branch, branch=branch)

    code_id = _code_schema_attribute_id(branch=branch)
    assert set(conflicts) == {f"data/{code_id}/parameters/value", f"data/{code_id}/regex/value"}
    assert {conflict.selected_branch for conflict in conflicts.values()} == {None}

    graph_merger = await build_graph_merger(db=db, source_branch=branch, destination_branch=default_branch)
    with pytest.raises(MergeConflictsUnresolvedError):
        await graph_merger.merge(at=Timestamp())


async def test_resolved_for_the_destination_the_merged_schema_keeps_the_destination_regex(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_local: WorkflowLocalExecution,
    register_core_models_schema: SchemaBranch,
) -> None:
    """The destination's own value satisfies its regex, so nothing is refused and the branch's edit is dropped."""
    _, branch = await _fork_then_change_the_regex_on_both_sides(
        db=db,
        default_branch=default_branch,
        branch_name="regex-conflict-keep-destination",
        destination_code="lowercase",
    )
    conflicts = await _conflicts(db=db, default_branch=default_branch, branch=branch)
    await _resolve_all(db=db, branch=branch, conflicts=conflicts, selection=ConflictSelection.BASE_BRANCH)

    analyzer = await build_schema_analyzer(db=db, source_branch=branch, destination_branch=default_branch)
    assert _code_regex(await analyzer.get_candidate_schema()) == LOWERCASE_ONLY

    graph_merger = await build_graph_merger(db=db, source_branch=branch, destination_branch=default_branch)
    await graph_merger.merge(at=Timestamp())

    merged_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    assert _code_regex(merged_schema) == LOWERCASE_ONLY


async def test_resolved_for_the_source_the_destination_data_is_checked_against_the_source_regex(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_local: WorkflowLocalExecution,
    register_core_models_schema: SchemaBranch,
) -> None:
    """The user picked the branch's regex; the destination's value breaks it, so the merge is refused.

    A conflict on the schema node's property must not hide the violation on the data that property
    governs: the two live on different nodes.
    """
    widget, branch = await _fork_then_change_the_regex_on_both_sides(
        db=db, default_branch=default_branch, branch_name="regex-conflict-take-source", destination_code="lowercase"
    )
    conflicts = await _conflicts(db=db, default_branch=default_branch, branch=branch)
    await _resolve_all(db=db, branch=branch, conflicts=conflicts, selection=ConflictSelection.DIFF_BRANCH)

    analyzer = await build_schema_analyzer(db=db, source_branch=branch, destination_branch=default_branch)
    assert _code_regex(await analyzer.get_candidate_schema()) == UPPERCASE_ONLY

    graph_merger = await build_graph_merger(db=db, source_branch=branch, destination_branch=default_branch)
    with pytest.raises(MergeConstraintsViolatedError) as exc_info:
        await graph_merger.merge(at=Timestamp())

    reported = {(conflict.type, conflict.id) for conflict in exc_info.value.schema_conflicts}
    assert (ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value, widget.id) in reported
    assert _code_regex(await registry.schema.load_schema_from_db(db=db, branch=default_branch)) == LOWERCASE_ONLY


async def test_resolved_for_the_source_the_merged_schema_takes_the_source_regex(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_local: WorkflowLocalExecution,
    register_core_models_schema: SchemaBranch,
) -> None:
    _, branch = await _fork_then_change_the_regex_on_both_sides(
        db=db, default_branch=default_branch, branch_name="regex-conflict-take-source-clean", destination_code=None
    )
    conflicts = await _conflicts(db=db, default_branch=default_branch, branch=branch)
    await _resolve_all(db=db, branch=branch, conflicts=conflicts, selection=ConflictSelection.DIFF_BRANCH)

    graph_merger = await build_graph_merger(db=db, source_branch=branch, destination_branch=default_branch)
    await graph_merger.merge(at=Timestamp())

    merged_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    assert _code_regex(merged_schema) == UPPERCASE_ONLY
