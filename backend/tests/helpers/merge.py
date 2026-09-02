"""Builders for the merge components a test needs to drive a real merge or schema comparison."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.diff_locker import DiffLocker
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.merge.constraints import MergeConstraintValidator
from infrahub.core.merge.graph_merger import GraphMerger
from infrahub.core.merge.schema_analyzer import MergeSchemaAnalyzer
from infrahub.core.validators.constraint_merge import build_constraint_info_merger
from infrahub.core.validators.determiner import build_constraint_validator_determiner
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.dependencies.registry import get_component_registry

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


async def build_schema_analyzer(
    db: InfrahubDatabase, source_branch: Branch, destination_branch: Branch
) -> MergeSchemaAnalyzer:
    component_registry = get_component_registry()
    return MergeSchemaAnalyzer(
        db=db,
        source_branch=source_branch,
        destination_branch=destination_branch,
        diff_repository=await component_registry.get_component(DiffRepository, db=db, branch=source_branch),
        schema_manager=registry.schema,
    )


async def build_graph_merger(db: InfrahubDatabase, source_branch: Branch, destination_branch: Branch) -> GraphMerger:
    component_registry = get_component_registry()
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=source_branch)
    return GraphMerger(
        db=db,
        source_branch=source_branch,
        destination_branch=destination_branch,
        diff_coordinator=await component_registry.get_component(DiffCoordinator, db=db, branch=source_branch),
        diff_merger=await component_registry.get_component(DiffMerger, db=db, branch=source_branch),
        diff_repository=diff_repository,
        diff_locker=DiffLocker(),
        schema_analyzer=await build_schema_analyzer(
            db=db, source_branch=source_branch, destination_branch=destination_branch
        ),
        constraint_validator=MergeConstraintValidator(
            branch=source_branch,
            diff_repository=diff_repository,
            determiner=build_constraint_validator_determiner(db=db, branch=source_branch),
            constraint_info_merger=build_constraint_info_merger(),
            migration_validator=schema_validate_migrations,
        ),
    )


async def set_attribute(
    db: InfrahubDatabase, branch: Branch, node_kind: str, attribute_name: str, **changes: Any
) -> None:
    """Assign properties on an attribute and persist the branch's schema.

    Values are assigned rather than overlaid, so a property can be cleared back to ``None``.
    """
    await _set_on_attribute(db=db, branch=branch, node_kind=node_kind, attribute_name=attribute_name, changes=changes)


async def set_attribute_parameters(
    db: InfrahubDatabase, branch: Branch, node_kind: str, attribute_name: str, **changes: Any
) -> None:
    """Assign properties on an attribute's ``parameters`` and persist the branch's schema."""
    await _set_on_attribute(
        db=db, branch=branch, node_kind=node_kind, attribute_name=attribute_name, changes=changes, on_parameters=True
    )


async def _set_on_attribute(
    db: InfrahubDatabase,
    branch: Branch,
    node_kind: str,
    attribute_name: str,
    changes: dict[str, Any],
    on_parameters: bool = False,
) -> None:
    schema = registry.schema.get_schema_branch(name=branch.name)
    node_schema = schema.get(name=node_kind)
    attribute = node_schema.get_attribute(name=attribute_name)
    target = attribute.parameters if on_parameters else attribute
    for name, value in changes.items():
        setattr(target, name, value)
    schema.set(name=node_kind, schema=node_schema)
    schema.process()
    await registry.schema.update_schema_branch(db=db, branch=branch, schema=schema, limit=[node_kind], update_db=True)
    branch.update_schema_hash()
    await branch.save(db=db)
