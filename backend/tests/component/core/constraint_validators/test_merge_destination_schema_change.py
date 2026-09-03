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
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.timestamp import Timestamp
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.exceptions import MergeConstraintsViolatedError
from tests.helpers.merge import build_graph_merger, build_schema_analyzer, set_attribute, set_attribute_parameters
from tests.helpers.schema import apply_schema_update, load_schema

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


def _widget_schema(code_name: str = "code", code_id: str | None = None) -> SchemaRoot:
    return SchemaRoot(
        nodes=[
            NodeSchema(
                name="Widget",
                namespace="Testing",
                default_filter="name__value",
                # The label must not read `code`, whose stored value stops parsing once the kind is narrowed
                display_labels=["name__value"],
                attributes=[
                    AttributeSchema(name="name", kind="Text"),
                    AttributeSchema(
                        id=code_id, name=code_name, kind="Text", optional=True, parameters=TextAttributeParameters()
                    ),
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


async def _widget_codes(db: InfrahubDatabase, branch: Branch) -> list[str | None]:
    widgets = await NodeManager.query(db=db, schema=WIDGET_KIND, branch=branch)
    return sorted((node.get_attribute("code").value for node in widgets), key=str)


async def _fork_with_one_widget(db: InfrahubDatabase, branch_name: str, code: str) -> tuple[Node, Branch]:
    lock.initialize_lock(local_only=True)
    await load_schema(db=db, schema=_widget_schema(), update_db=True)
    widget = await Node.init(db=db, schema=WIDGET_KIND)
    await widget.new(db=db, name="widget-one", code=code)
    await widget.save(db=db)
    return widget, await create_branch(db=db, branch_name=branch_name)


async def _add_branch_widget(db: InfrahubDatabase, branch: Branch, code: str | None) -> Node:
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=branch)
    await widget.new(db=db, name="widget-on-branch", code=code)
    await widget.save(db=db)
    return widget


class TestDestinationNarrowedTheAttribute:
    """The destination narrows a property gated on a migration after the fork; the branch's data breaks it.

    These properties produce a migration entry rather than a constraint, so the check only runs if the
    schema comparison converts it back into one. Each case forks from a destination whose own data
    satisfies the change, so the branch's row is the only offender.
    """

    async def test_an_attribute_made_unique(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        workflow_local: WorkflowLocalExecution,
        register_core_models_schema: SchemaBranch,
    ) -> None:
        widget, branch = await _fork_with_one_widget(db=db, branch_name="dest-made-code-unique", code="42")
        await set_attribute(db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", unique=True)
        offender = await _add_branch_widget(db=db, branch=branch, code="42")

        graph_merger = await build_graph_merger(db=db, source_branch=branch, destination_branch=default_branch)
        with pytest.raises(MergeConstraintsViolatedError) as exc_info:
            await graph_merger.merge(at=Timestamp())

        assert {(conflict.type, conflict.id) for conflict in exc_info.value.schema_conflicts} == {
            ("attribute.unique.update", widget.id),
            ("attribute.unique.update", offender.id),
            (ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value, widget.id),
            (ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value, offender.id),
        }
        assert await _widget_codes(db=db, branch=default_branch) == ["42"]
        assert await _widget_codes(db=db, branch=branch) == ["42", "42"]

    async def test_an_attribute_kind_narrowed(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        workflow_local: WorkflowLocalExecution,
        register_core_models_schema: SchemaBranch,
    ) -> None:
        # The destination's own widget carries no value: narrowing the kind through the API would have
        # migrated its stored text, and `set_attribute` runs no migrations.
        _, branch = await _fork_with_one_widget(db=db, branch_name="dest-narrowed-code-kind", code=None)
        await set_attribute(db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", kind="Number")
        offender = await _add_branch_widget(db=db, branch=branch, code="not-a-number")

        graph_merger = await build_graph_merger(db=db, source_branch=branch, destination_branch=default_branch)
        with pytest.raises(MergeConstraintsViolatedError) as exc_info:
            await graph_merger.merge(at=Timestamp())

        assert {(conflict.type, conflict.id) for conflict in exc_info.value.schema_conflicts} == {
            ("attribute.kind.update", offender.id)
        }
        assert await _widget_codes(db=db, branch=default_branch) == [None]

    async def test_an_attribute_made_mandatory(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        workflow_local: WorkflowLocalExecution,
        register_core_models_schema: SchemaBranch,
    ) -> None:
        _, branch = await _fork_with_one_widget(db=db, branch_name="dest-made-code-mandatory", code="42")
        await set_attribute(db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", optional=False)
        offender = await _add_branch_widget(db=db, branch=branch, code=None)

        graph_merger = await build_graph_merger(db=db, source_branch=branch, destination_branch=default_branch)
        with pytest.raises(MergeConstraintsViolatedError) as exc_info:
            await graph_merger.merge(at=Timestamp())

        assert {(conflict.type, conflict.id) for conflict in exc_info.value.schema_conflicts} == {
            ("attribute.optional.update", offender.id)
        }
        assert await _widget_codes(db=db, branch=default_branch) == ["42"]


async def test_a_cosmetic_destination_change_schedules_nothing(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_local: WorkflowLocalExecution,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A destination change no constraint guards opens the gate and then has nothing to say.

    The gate is a plain hash comparison, so it opens for a description edit like any other. What
    matters is that the comparison behind it schedules no check and no migration, and the merge of a
    data-only branch goes through.
    """
    _, branch = await _fork_with_one_widget(db=db, branch_name="dest-cosmetic-change", code="42")
    await set_attribute(
        db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", description="The widget's code"
    )
    await _add_branch_widget(db=db, branch=branch, code="43")

    analyzer = await build_schema_analyzer(db=db, source_branch=branch, destination_branch=default_branch)
    assert analyzer.schemas_differ() is True
    assert await analyzer.calculate_validations() == []
    assert await analyzer.calculate_migrations() == []

    graph_merger = await build_graph_merger(db=db, source_branch=branch, destination_branch=default_branch)
    await graph_merger.merge(at=Timestamp())

    assert await _widget_codes(db=db, branch=default_branch) == ["42", "43"]
    merged_code = registry.schema.get_node_schema(name=WIDGET_KIND, branch=default_branch).get_attribute(name="code")
    assert merged_code.description == "The widget's code"


async def test_a_source_rename_meets_a_destination_change_on_the_same_attribute(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_local: WorkflowLocalExecution,
    register_core_models_schema: SchemaBranch,
) -> None:
    """The branch renames the attribute the destination tightened; the check runs under the new name.

    Each side's diff is keyed by the names of the schema it is compared with, so the two sides can
    only meet on the candidate: it holds the attribute under the branch's name with the destination's
    regex, and the violation is reported against that path.
    """
    _, branch = await _fork_with_one_widget(db=db, branch_name="source-renamed-dest-tightened", code="ALPHA")
    code_id = registry.schema.get_node_schema(name=WIDGET_KIND, branch=branch).get_attribute(name="code").id
    await apply_schema_update(
        db=db, schema=_widget_schema(code_name="identifier", code_id=code_id), branch_name=branch.name
    )
    await set_attribute_parameters(
        db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", regex=UPPERCASE_ONLY
    )
    offender = await Node.init(db=db, schema=WIDGET_KIND, branch=branch)
    await offender.new(db=db, name="widget-on-branch", identifier=BRANCH_VALUE)
    await offender.save(db=db)

    analyzer = await build_schema_analyzer(db=db, source_branch=branch, destination_branch=default_branch)
    candidate_widget = (await analyzer.get_candidate_schema()).get(name=WIDGET_KIND)
    assert {attr.name for attr in candidate_widget.attributes} == {"name", "identifier"}
    parameters = candidate_widget.get_attribute(name="identifier").parameters
    assert isinstance(parameters, TextAttributeParameters)
    assert parameters.regex == UPPERCASE_ONLY

    graph_merger = await build_graph_merger(db=db, source_branch=branch, destination_branch=default_branch)
    with pytest.raises(MergeConstraintsViolatedError) as exc_info:
        await graph_merger.merge(at=Timestamp())

    reported = {(conflict.type, conflict.id, conflict.name) for conflict in exc_info.value.schema_conflicts}
    assert (
        ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value,
        offender.id,
        f"schema/{WIDGET_KIND}/identifier/parameters.regex",
    ) in reported
    # Every path speaks of the attribute as the candidate names it; the old name cannot be resolved there.
    assert {name.split("/")[2] for _, _, name in reported} == {"identifier"}
    assert await _widget_codes(db=db, branch=default_branch) == ["ALPHA"]
