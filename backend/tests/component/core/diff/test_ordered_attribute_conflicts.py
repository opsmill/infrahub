"""End-to-end conflict detection for order-(in)sensitive list attributes via DiffCoordinator.

List-valued attributes are changed on a branch and on main, then the diff is computed. An attribute
flagged ``ordered=False`` must not report a conflict when the two sides hold the same elements in a
different order; an attribute with the default ordered behavior must still report one. Conflicts are
re-evaluated against the live values on every recompute, so a conflict recorded during a real
divergence is cleared once the two sides converge.

These are slow component tests whose cost is dominated by the per-test database reset plus
core-schema reload, so related scenarios are grouped into one test to share that setup rather than
split one-per-function.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from infrahub.core import registry
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.data_check_synchronizer import DiffDataCheckSynchronizer
from infrahub.core.diff.model.path import BranchTrackingId
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.dropdown import DropdownChoice
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffNode, EnrichedDiffRoot
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

WIDGET_KIND = "TestingWidget"


def _base_schema() -> SchemaRoot:
    return SchemaRoot(
        nodes=[
            NodeSchema(
                name="Widget",
                namespace="Testing",
                include_in_menu=False,
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="tags", kind="List", optional=True, ordered=False),
                    AttributeSchema(name="sequence", kind="List", optional=True),
                    AttributeSchema(
                        name="status", kind="Dropdown", optional=True, choices=[DropdownChoice(name="active")]
                    ),
                ],
            )
        ]
    )


async def _get_diff_coordinator(db: InfrahubDatabase, branch: Branch) -> DiffCoordinator:
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    diff_coordinator.data_check_synchronizer = AsyncMock(spec=DiffDataCheckSynchronizer)
    return diff_coordinator


async def _get_branch_diff(db: InfrahubDatabase, branch: Branch) -> EnrichedDiffRoot:
    component_registry = get_component_registry()
    diff_repo = await component_registry.get_component(DiffRepository, db=db, branch=branch)
    return await diff_repo.get_one(tracking_id=BranchTrackingId(name=branch.name), diff_branch_name=branch.name)


async def _set_node_values(db: InfrahubDatabase, branch: Branch, node_id: str, **values: list[str]) -> None:
    node = await NodeManager.get_one(db=db, branch=branch, id=node_id)
    assert node is not None
    for name, value in values.items():
        node.get_attribute(name).value = value
    await node.save(db=db)


async def _set_status_choices(db: InfrahubDatabase, branch: Branch, choice_names: list[str]) -> None:
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    widget = schema_branch.get(name=WIDGET_KIND, duplicate=True)
    widget.get_attribute("status").choices = [DropdownChoice(name=name) for name in choice_names]
    schema_branch.set(name=WIDGET_KIND, schema=widget)
    schema_branch.process()
    await registry.schema.update_schema_branch(
        schema=schema_branch, db=db, branch=branch, limit=[WIDGET_KIND], update_db=True
    )
    branch.update_schema_hash()
    await branch.save(db=db)


def _value_conflict(diff_node: EnrichedDiffNode | None, attribute_name: str) -> object | None:
    if diff_node is None:
        return None
    for attribute in diff_node.attributes:
        if attribute.name != attribute_name:
            continue
        for prop in attribute.properties:
            if prop.property_type is DatabaseEdgeType.HAS_VALUE:
                return prop.conflict
    return None


async def _node_value_conflict(
    db: InfrahubDatabase, branch: Branch, node_id: str, attribute_name: str
) -> object | None:
    diff = await _get_branch_diff(db=db, branch=branch)
    node = {n.uuid: n for n in diff.nodes}.get(node_id)
    return _value_conflict(node, attribute_name)


def _status_attr_id(branch: Branch) -> str:
    gadget = registry.schema.get(name=WIDGET_KIND, branch=branch.name, duplicate=False)
    return gadget.get_attribute("status").get_id()


async def test_data_attribute_list_conflicts(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Order-(in)sensitive conflict behavior for list attributes on data nodes.

    Grouped scenarios sharing one setup:
      - a fresh reorder of the same elements conflicts for an ordered attribute but not for an
        ``ordered=False`` one;
      - after a real divergence, an ordered attribute stays conflicted while the two values differ
        (same set, different order) and clears once they become byte-identical, showing the recompute
        re-evaluates the live values rather than carrying the earlier conflict forward.
    """
    await load_schema(db=db, schema=_base_schema(), update_db=True)

    reorder_widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await reorder_widget.new(db=db, name="reorder", tags=["a", "b", "c"], sequence=["x", "y", "z"])
    await reorder_widget.save(db=db)
    reorder_id = reorder_widget.get_id()

    recompute_widget = await Node.init(db=db, schema=WIDGET_KIND, branch=default_branch)
    await recompute_widget.new(db=db, name="recompute", sequence=["a"])
    await recompute_widget.save(db=db)
    recompute_id = recompute_widget.get_id()

    reorder_branch = await create_branch(db=db, branch_name="reorder-branch")
    await _set_node_values(
        db=db, branch=reorder_branch, node_id=reorder_id, tags=["c", "a", "b"], sequence=["z", "x", "y"]
    )
    await _set_node_values(
        db=db, branch=default_branch, node_id=reorder_id, tags=["b", "c", "a"], sequence=["y", "z", "x"]
    )
    reorder_coordinator = await _get_diff_coordinator(db=db, branch=reorder_branch)
    await reorder_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=reorder_branch)
    reorder_diff = await _get_branch_diff(db=db, branch=reorder_branch)
    reorder_node = {n.uuid: n for n in reorder_diff.nodes}[reorder_id]
    assert _value_conflict(reorder_node, "tags") is None
    assert _value_conflict(reorder_node, "sequence") is not None

    recompute_branch = await create_branch(db=db, branch_name="recompute-branch")
    recompute_coordinator = await _get_diff_coordinator(db=db, branch=recompute_branch)

    async def _recompute_conflict() -> object | None:
        await recompute_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=recompute_branch)
        return await _node_value_conflict(
            db=db, branch=recompute_branch, node_id=recompute_id, attribute_name="sequence"
        )

    await _set_node_values(db=db, branch=default_branch, node_id=recompute_id, sequence=["a", "main_only"])
    await _set_node_values(db=db, branch=recompute_branch, node_id=recompute_id, sequence=["a", "feature_only"])
    assert await _recompute_conflict() is not None

    await _set_node_values(
        db=db, branch=recompute_branch, node_id=recompute_id, sequence=["a", "feature_only", "main_only"]
    )
    await _set_node_values(
        db=db, branch=default_branch, node_id=recompute_id, sequence=["a", "main_only", "feature_only"]
    )
    assert await _recompute_conflict() is not None

    await _set_node_values(
        db=db, branch=recompute_branch, node_id=recompute_id, sequence=["a", "main_only", "feature_only"]
    )
    assert await _recompute_conflict() is None


async def test_dropdown_choices_conflicts_cleared_on_recompute_paths(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """A converged ``ordered=False`` Dropdown.choices conflict is cleared on both recompute entry points.

    Two branches diverge to different choice sets (a real conflict), then converge to the same set in a
    different order. Grouped scenarios sharing one setup exercise the two ways a diff is recomputed:
      - ``update_branch_diff`` (the incremental-update path), which re-runs the enricher;
      - ``recalculate`` (the path that transfers prior conflicts onto the fresh diff).
    Neither keeps the converged conflict.
    """
    await load_schema(db=db, schema=_base_schema(), update_db=True)

    update_branch = await create_branch(db=db, branch_name="choices-update")
    update_coordinator = await _get_diff_coordinator(db=db, branch=update_branch)
    await _set_status_choices(db=db, branch=default_branch, choice_names=["active", "main_only"])
    await _set_status_choices(db=db, branch=update_branch, choice_names=["active", "feature_only"])
    await update_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=update_branch)
    assert (
        await _node_value_conflict(
            db=db, branch=update_branch, node_id=_status_attr_id(update_branch), attribute_name="choices"
        )
    ) is not None
    await _set_status_choices(db=db, branch=update_branch, choice_names=["active", "feature_only", "main_only"])
    await _set_status_choices(db=db, branch=default_branch, choice_names=["active", "main_only", "feature_only"])
    await update_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=update_branch)
    assert (
        await _node_value_conflict(
            db=db, branch=update_branch, node_id=_status_attr_id(update_branch), attribute_name="choices"
        )
    ) is None

    recalc_branch = await create_branch(db=db, branch_name="choices-recalc")
    recalc_coordinator = await _get_diff_coordinator(db=db, branch=recalc_branch)
    await _set_status_choices(db=db, branch=default_branch, choice_names=["active", "red"])
    await _set_status_choices(db=db, branch=recalc_branch, choice_names=["active", "blue"])
    await recalc_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=recalc_branch)
    stored = await _get_branch_diff(db=db, branch=recalc_branch)
    assert _value_conflict({n.uuid: n for n in stored.nodes}.get(_status_attr_id(recalc_branch)), "choices") is not None
    await _set_status_choices(db=db, branch=recalc_branch, choice_names=["active", "blue", "red"])
    await _set_status_choices(db=db, branch=default_branch, choice_names=["active", "red", "blue"])
    await recalc_coordinator.recalculate(base_branch=default_branch, diff_branch=recalc_branch, diff_id=stored.uuid)
    assert (
        await _node_value_conflict(
            db=db, branch=recalc_branch, node_id=_status_attr_id(recalc_branch), attribute_name="choices"
        )
    ) is None
