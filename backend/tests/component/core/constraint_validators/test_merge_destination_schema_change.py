"""Merging a branch into a destination whose schema changed after the branch forked.

The branch's data was written under the schema it forked with, so a property the destination has
changed since is one that data has never been checked against. Covers the merge refusing that data,
and the merged schema the check is evaluated against.

Two shapes matter because they fail differently. Where the destination *sets* a property the branch
leaves unset, the destination's value survives a plain overlay of the two schemas. Where the
destination *replaces* a value the branch also holds, a plain overlay writes the branch's older value
back and the check has nothing left to catch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub import lock
from infrahub.core import registry
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.diff_locker import DiffLocker
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge.constraints import MergeConstraintValidator
from infrahub.core.merge.graph_merger import GraphMerger
from infrahub.core.merge.schema_analyzer import MergeSchemaAnalyzer
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.constraint_merge import build_constraint_info_merger
from infrahub.core.validators.determiner import build_constraint_validator_determiner
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.dependencies.registry import get_component_registry
from infrahub.exceptions import MergeConstraintsViolatedError
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.services.adapters.workflow.local import WorkflowLocalExecution

WIDGET_KIND = "TestingWidget"
PERMISSIVE = r".*"
UPPERCASE_ONLY = r"^[A-Z]+$"
DESTINATION_VALUE = "ALPHA"
BRANCH_VALUE = "lowercase"


def _widget_schema() -> SchemaRoot:
    return SchemaRoot(
        nodes=[
            NodeSchema(
                name="Widget",
                namespace="Testing",
                default_filter="name__value",
                attributes=[
                    AttributeSchema(name="name", kind="Text"),
                    AttributeSchema(name="code", kind="Text", optional=True, parameters=TextAttributeParameters()),
                ],
            )
        ]
    )


async def _set_regex(db: InfrahubDatabase, branch: Branch, regex: str | None) -> None:
    """Set ``code``'s regex on one branch, assigning the value rather than overlaying a schema.

    An overlay cannot clear a property, so tests that need the branches to start from an unset regex
    have to assign it directly.
    """
    schema = registry.schema.get_schema_branch(name=branch.name)
    node_schema = schema.get(name=WIDGET_KIND)
    parameters = node_schema.get_attribute(name="code").parameters
    assert isinstance(parameters, TextAttributeParameters)
    parameters.regex = regex
    schema.set(name=WIDGET_KIND, schema=node_schema)
    schema.process()
    await registry.schema.update_schema_branch(db=db, branch=branch, schema=schema, limit=[WIDGET_KIND], update_db=True)
    branch.update_schema_hash()
    await branch.save(db=db)


def _code_regex(schema: SchemaBranch) -> str | None:
    parameters = schema.get(name=WIDGET_KIND).get_attribute(name="code").parameters
    assert isinstance(parameters, TextAttributeParameters)
    return parameters.regex


async def _build_schema_analyzer(
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


async def _build_graph_merger(db: InfrahubDatabase, source_branch: Branch, destination_branch: Branch) -> GraphMerger:
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
        schema_analyzer=await _build_schema_analyzer(
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


class TestDestinationSchemaChange:
    """One widget on the destination, and a branch forked from it per case.

    Every test sets the destination's regex to the value it wants the branch to fork with, so the
    order the tests run in makes no difference.
    """

    @pytest.fixture(scope="class")
    async def widget(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> Node:
        lock.initialize_lock(local_only=True)
        await load_schema(db=db, schema=_widget_schema(), update_db=True)
        widget = await Node.init(db=db, schema=WIDGET_KIND)
        await widget.new(db=db, name="widget-one", code=DESTINATION_VALUE)
        await widget.save(db=db)
        return widget

    async def _fork_after_destination_change(
        self,
        db: InfrahubDatabase,
        destination: Branch,
        widget: Node,
        branch_name: str,
        forked_regex: str | None,
    ) -> Branch:
        """Fork at ``forked_regex``, tighten the destination, then write a value only the branch allows.

        The write is legal under the branch's own schema, and the destination's own data satisfies its
        new regex, so neither side rejects anything in isolation.
        """
        await _set_regex(db=db, branch=destination, regex=forked_regex)
        branch = await create_branch(db=db, branch_name=branch_name)
        await _set_regex(db=db, branch=destination, regex=UPPERCASE_ONLY)

        branch_widget = await NodeManager.get_one(db=db, id=widget.id, branch=branch, raise_on_error=True)
        branch_widget.get_attribute("code").value = BRANCH_VALUE
        await branch_widget.save(db=db)
        return branch

    async def _destination_code_values(self, db: InfrahubDatabase, destination: Branch) -> list[str]:
        widgets = await NodeManager.query(db=db, schema=WIDGET_KIND, branch=destination)
        return sorted(str(node.get_attribute("code").value) for node in widgets)

    async def test_merge_is_blocked_when_the_destination_set_a_property(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        widget: Node,
        workflow_local: WorkflowLocalExecution,
    ) -> None:
        branch = await self._fork_after_destination_change(
            db=db,
            destination=default_branch_scope_class,
            widget=widget,
            branch_name="dest-set-regex",
            forked_regex=None,
        )
        graph_merger = await _build_graph_merger(
            db=db, source_branch=branch, destination_branch=default_branch_scope_class
        )

        with pytest.raises(MergeConstraintsViolatedError):
            await graph_merger.merge(at=Timestamp())

        assert await self._destination_code_values(db=db, destination=default_branch_scope_class) == [DESTINATION_VALUE]

    async def test_merge_is_blocked_when_the_destination_replaced_a_property(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        widget: Node,
        workflow_local: WorkflowLocalExecution,
    ) -> None:
        """The shape a plain overlay gets wrong: the branch's older value is not ``None``."""
        branch = await self._fork_after_destination_change(
            db=db,
            destination=default_branch_scope_class,
            widget=widget,
            branch_name="dest-replace-regex",
            forked_regex=PERMISSIVE,
        )
        graph_merger = await _build_graph_merger(
            db=db, source_branch=branch, destination_branch=default_branch_scope_class
        )

        with pytest.raises(MergeConstraintsViolatedError):
            await graph_merger.merge(at=Timestamp())

        assert await self._destination_code_values(db=db, destination=default_branch_scope_class) == [DESTINATION_VALUE]

    async def test_the_candidate_schema_keeps_the_destination_value(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, widget: Node
    ) -> None:
        branch = await self._fork_after_destination_change(
            db=db,
            destination=default_branch_scope_class,
            widget=widget,
            branch_name="candidate-replace-regex",
            forked_regex=PERMISSIVE,
        )
        analyzer = await _build_schema_analyzer(
            db=db, source_branch=branch, destination_branch=default_branch_scope_class
        )

        assert analyzer.schemas_differ() is True
        assert _code_regex(await analyzer.get_candidate_schema()) == UPPERCASE_ONLY

    async def test_identical_changes_on_both_sides_leave_nothing_to_compare(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, widget: Node
    ) -> None:
        """Each side validated its own data when it loaded the change."""
        await _set_regex(db=db, branch=default_branch_scope_class, regex=PERMISSIVE)
        branch = await create_branch(db=db, branch_name="converged-edits")
        for target in (default_branch_scope_class, branch):
            await _set_regex(db=db, branch=target, regex=UPPERCASE_ONLY)

        analyzer = await _build_schema_analyzer(
            db=db, source_branch=branch, destination_branch=default_branch_scope_class
        )

        assert analyzer.schemas_differ() is False
        assert _code_regex(await analyzer.get_candidate_schema()) == UPPERCASE_ONLY
