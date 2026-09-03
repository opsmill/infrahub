"""Rebasing a branch onto a destination whose schema changed after the branch forked.

The branch's data was written under the schema it forked with, so a property the destination has
changed since is one that data has never been checked against. A rebase writes the destination's
schema onto the branch, so it has to be refused up front, before anything moves, rather than run to
completion and fail in the post-rebase diff refresh.

Every refusal test pins three things: the constraint that refused, that the offending row is still on
the branch, and that the fork point did not move.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.branch.tasks import rebase_branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import TextAttributeParameters
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.exceptions import ValidationError
from infrahub.workers.dependencies import build_database
from tests.helpers.merge import build_schema_analyzer, set_attribute, set_attribute_parameters
from tests.helpers.schema import apply_schema_update, load_schema

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowAwaitedOnly

WIDGET_KIND = "TestingWidget"
PERMISSIVE = r".*"
UPPERCASE_ONLY = r"^[A-Z]+$"


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


async def _fork_with_one_widget(
    db: InfrahubDatabase, branch_name: str, code: str | None, code_regex: str | None = None
) -> tuple[Node, Branch]:
    lock.initialize_lock(local_only=True)
    await load_schema(db=db, schema=_widget_schema(), update_db=True)
    if code_regex is not None:
        await set_attribute_parameters(
            db=db,
            branch=registry.get_branch_from_registry(),
            node_kind=WIDGET_KIND,
            attribute_name="code",
            regex=code_regex,
        )
    widget = await Node.init(db=db, schema=WIDGET_KIND)
    await widget.new(db=db, name="widget-one", code=code)
    await widget.save(db=db)
    return widget, await create_branch(db=db, branch_name=branch_name)


async def _add_branch_widget(db: InfrahubDatabase, branch: Branch, **values: str | None) -> Node:
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=branch)
    await widget.new(db=db, name="widget-on-branch", **values)
    await widget.save(db=db)
    return widget


async def _rebase(db: InfrahubDatabase, dependency_provider: Provider, default_branch: Branch, branch: Branch) -> None:
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    with dependency_provider.scope(build_database, lambda singleton=True: db):  # noqa: ARG005
        await rebase_branch(branch=branch.name, context=context)


async def _refused_rebase(
    db: InfrahubDatabase, dependency_provider: Provider, default_branch: Branch, branch: Branch
) -> str:
    """Rebase, expect a refusal, and check the branch is exactly as it was."""
    with pytest.raises(ValidationError) as exc_info:
        await _rebase(db=db, dependency_provider=dependency_provider, default_branch=default_branch, branch=branch)
    message = exc_info.value.message
    assert "for constraint" in message, "the rebase is refused by constraint validation"
    refused_branch = await Branch.get_by_name(db=db, name=branch.name)
    assert refused_branch.branched_from == branch.branched_from, "a refused rebase moves no fork point"
    return message


def _offenders(message: str) -> set[str]:
    return set(re.findall(r"and node (\S+) ", message))


def _constraints(message: str) -> set[str]:
    return set(re.findall(r"for constraint (\S+) ", message))


class TestDestinationChangedARegex:
    async def test_the_destination_set_a_regex(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        workflow_awaited_only: WorkflowAwaitedOnly,
        dependency_provider: Provider,
        register_core_models_schema: SchemaBranch,
    ) -> None:
        _, branch = await _fork_with_one_widget(db=db, branch_name="dest-set-regex-rebase", code="ALPHA")
        await set_attribute_parameters(
            db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", regex=UPPERCASE_ONLY
        )
        offender = await _add_branch_widget(db=db, branch=branch, code="lowercase")

        message = await _refused_rebase(
            db=db, dependency_provider=dependency_provider, default_branch=default_branch, branch=branch
        )

        assert _offenders(message) == {offender.id}
        assert ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value in _constraints(message)
        assert await NodeManager.count(db=db, schema=WIDGET_KIND, branch=branch) == 2

    async def test_the_destination_replaced_a_regex(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        workflow_awaited_only: WorkflowAwaitedOnly,
        dependency_provider: Provider,
        register_core_models_schema: SchemaBranch,
    ) -> None:
        """The shape a plain overlay gets wrong: the branch's older value is not ``None``."""
        _, branch = await _fork_with_one_widget(
            db=db, branch_name="dest-replaced-regex-rebase", code="ALPHA", code_regex=PERMISSIVE
        )
        await set_attribute_parameters(
            db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", regex=UPPERCASE_ONLY
        )
        offender = await _add_branch_widget(db=db, branch=branch, code="lowercase")

        message = await _refused_rebase(
            db=db, dependency_provider=dependency_provider, default_branch=default_branch, branch=branch
        )

        assert _offenders(message) == {offender.id}
        assert ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value in _constraints(message)
        assert await NodeManager.count(db=db, schema=WIDGET_KIND, branch=branch) == 2


class TestDestinationNarrowedTheAttribute:
    """Properties gated on a migration, which only reach the check through the schema comparison."""

    async def test_an_attribute_made_unique(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        workflow_awaited_only: WorkflowAwaitedOnly,
        dependency_provider: Provider,
        register_core_models_schema: SchemaBranch,
    ) -> None:
        widget, branch = await _fork_with_one_widget(db=db, branch_name="dest-made-unique-rebase", code="42")
        await set_attribute(db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", unique=True)
        offender = await _add_branch_widget(db=db, branch=branch, code="42")

        message = await _refused_rebase(
            db=db, dependency_provider=dependency_provider, default_branch=default_branch, branch=branch
        )

        assert _offenders(message) == {widget.id, offender.id}
        assert _constraints(message) == {
            "attribute.unique.update",
            ConstraintIdentifier.NODE_UNIQUENESS_CONSTRAINTS_UPDATE.value,
        }

    async def test_an_attribute_kind_narrowed(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        workflow_awaited_only: WorkflowAwaitedOnly,
        dependency_provider: Provider,
        register_core_models_schema: SchemaBranch,
    ) -> None:
        # The destination's own widget carries no value: narrowing the kind through the API would have
        # migrated its stored text, and `set_attribute` runs no migrations.
        _, branch = await _fork_with_one_widget(db=db, branch_name="dest-narrowed-kind-rebase", code=None)
        await set_attribute(db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", kind="Number")
        offender = await _add_branch_widget(db=db, branch=branch, code="not-a-number")

        message = await _refused_rebase(
            db=db, dependency_provider=dependency_provider, default_branch=default_branch, branch=branch
        )

        assert _offenders(message) == {offender.id}
        assert _constraints(message) == {"attribute.kind.update"}

    async def test_an_attribute_made_mandatory(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        workflow_awaited_only: WorkflowAwaitedOnly,
        dependency_provider: Provider,
        register_core_models_schema: SchemaBranch,
    ) -> None:
        _, branch = await _fork_with_one_widget(db=db, branch_name="dest-made-mandatory-rebase", code="42")
        await set_attribute(db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", optional=False)
        offender = await _add_branch_widget(db=db, branch=branch, code=None)

        message = await _refused_rebase(
            db=db, dependency_provider=dependency_provider, default_branch=default_branch, branch=branch
        )

        assert _offenders(message) == {offender.id}
        assert _constraints(message) == {"attribute.optional.update"}


async def test_a_cosmetic_destination_change_schedules_nothing(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_awaited_only: WorkflowAwaitedOnly,
    dependency_provider: Provider,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A destination change no constraint guards opens the gate and then has nothing to say."""
    _, branch = await _fork_with_one_widget(db=db, branch_name="dest-cosmetic-rebase", code="42")
    await set_attribute(
        db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", description="The widget's code"
    )
    await _add_branch_widget(db=db, branch=branch, code="43")

    analyzer = await build_schema_analyzer(db=db, source_branch=branch, destination_branch=default_branch)
    assert analyzer.schemas_differ() is True
    assert await analyzer.calculate_validations() == []
    assert await analyzer.calculate_migrations() == []

    await _rebase(db=db, dependency_provider=dependency_provider, default_branch=default_branch, branch=branch)

    rebased_branch = await Branch.get_by_name(db=db, name=branch.name)
    assert rebased_branch.branched_from > branch.branched_from
    rebased_code = registry.schema.get_node_schema(name=WIDGET_KIND, branch=rebased_branch).get_attribute(name="code")
    assert rebased_code.description == "The widget's code"
    widgets = await NodeManager.query(db=db, schema=WIDGET_KIND, branch=rebased_branch)
    assert sorted(str(node.get_attribute("code").value) for node in widgets) == ["42", "43"]


async def test_a_source_rename_meets_a_destination_change_on_the_same_attribute(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_awaited_only: WorkflowAwaitedOnly,
    dependency_provider: Provider,
    register_core_models_schema: SchemaBranch,
) -> None:
    """The branch renames the attribute the destination tightened; the check runs under the new name."""
    _, branch = await _fork_with_one_widget(db=db, branch_name="source-renamed-dest-tightened-rebase", code="ALPHA")
    code_id = registry.schema.get_node_schema(name=WIDGET_KIND, branch=branch).get_attribute(name="code").id
    await apply_schema_update(
        db=db, schema=_widget_schema(code_name="identifier", code_id=code_id), branch_name=branch.name
    )
    await set_attribute_parameters(
        db=db, branch=default_branch, node_kind=WIDGET_KIND, attribute_name="code", regex=UPPERCASE_ONLY
    )
    offender = await _add_branch_widget(db=db, branch=branch, identifier="lowercase")

    message = await _refused_rebase(
        db=db, dependency_provider=dependency_provider, default_branch=default_branch, branch=branch
    )

    assert _offenders(message) == {offender.id}
    assert ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value in _constraints(message)
    # Every path speaks of the attribute as the candidate names it; the old name cannot be resolved there.
    assert set(re.findall(r"for constraint \S+ (\S+) ", message)) == {"identifier"}
