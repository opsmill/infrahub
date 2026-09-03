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
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.timestamp import Timestamp
from infrahub.exceptions import MergeConstraintsViolatedError
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


def _code_regex(schema: SchemaBranch) -> str | None:
    parameters = schema.get(name=WIDGET_KIND).get_attribute(name="code").parameters
    assert isinstance(parameters, TextAttributeParameters)
    return parameters.regex


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
        await set_attribute_parameters(
            db=db, branch=destination, node_kind=WIDGET_KIND, attribute_name="code", regex=forked_regex
        )
        branch = await create_branch(db=db, branch_name=branch_name)
        await set_attribute_parameters(
            db=db, branch=destination, node_kind=WIDGET_KIND, attribute_name="code", regex=UPPERCASE_ONLY
        )

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
        graph_merger = await build_graph_merger(
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
        graph_merger = await build_graph_merger(
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
        analyzer = await build_schema_analyzer(
            db=db, source_branch=branch, destination_branch=default_branch_scope_class
        )

        assert analyzer.schemas_differ() is True
        assert _code_regex(await analyzer.get_candidate_schema()) == UPPERCASE_ONLY

    async def test_identical_changes_on_both_sides_leave_nothing_to_compare(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, widget: Node
    ) -> None:
        """Each side validated its own data when it loaded the change."""
        await set_attribute_parameters(
            db=db, branch=default_branch_scope_class, node_kind=WIDGET_KIND, attribute_name="code", regex=PERMISSIVE
        )
        branch = await create_branch(db=db, branch_name="converged-edits")
        for target in (default_branch_scope_class, branch):
            await set_attribute_parameters(
                db=db, branch=target, node_kind=WIDGET_KIND, attribute_name="code", regex=UPPERCASE_ONLY
            )

        analyzer = await build_schema_analyzer(
            db=db, source_branch=branch, destination_branch=default_branch_scope_class
        )

        assert analyzer.schemas_differ() is False
        assert _code_regex(await analyzer.get_candidate_schema()) == UPPERCASE_ONLY
