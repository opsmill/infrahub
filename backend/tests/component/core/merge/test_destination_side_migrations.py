"""Schema changes made on the destination after the fork, migrated over the rows a merge lands.

The post-merge migrations cover both sides of the fork, so their baseline has to be the common
ancestor: measured from the destination's own pre-merge schema, a destination-side removal cannot
find the previous version of the kind and a destination-side rename has already happened, leaving the
rows the merge just brought in untouched.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from infrahub import lock
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core import registry
from infrahub.core.branch.tasks import merge_branch
from infrahub.core.constants import HashableModelState
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.workers.dependencies import build_cache, build_database, build_event_service
from tests.adapters.cache import MemoryCache
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.schema import apply_schema_update, load_schema

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowAwaitedOnly

WIDGET_KIND = "TestingWidget"
GADGET_KIND = "TestingGadget"


def _widget(code_name: str = "code", code_id: str | None = None) -> NodeSchema:
    return NodeSchema(
        name="Widget",
        namespace="Testing",
        default_filter="name__value",
        display_labels=["name__value"],
        attributes=[
            AttributeSchema(name="name", kind="Text"),
            AttributeSchema(id=code_id, name=code_name, kind="Text", optional=True),
        ],
    )


def _gadget(state: HashableModelState = HashableModelState.PRESENT) -> NodeSchema:
    return NodeSchema(
        name="Gadget",
        namespace="Testing",
        default_filter="name__value",
        state=state,
        attributes=[AttributeSchema(name="name", kind="Text")],
    )


async def _merge(db: InfrahubDatabase, dependency_provider: Provider, default_branch: Branch, branch: Branch) -> None:
    context = InfrahubContext.init(
        branch=default_branch,
        account=AccountSession(account_id=str(uuid4()), auth_type=AuthType.NONE),
    )
    event_recorder = MemoryInfrahubEvent()
    cache = MemoryCache()
    with (
        dependency_provider.scope(build_database, lambda singleton=True: db),  # noqa: ARG005
        dependency_provider.scope(build_event_service, lambda: event_recorder),
        dependency_provider.scope(build_cache, lambda: cache),
    ):
        await merge_branch(branch=branch.name, context=context)


async def test_a_kind_the_destination_removed_after_the_fork_merges_cleanly(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_awaited_only: WorkflowAwaitedOnly,
    dependency_provider: Provider,
    register_core_models_schema: SchemaBranch,
) -> None:
    """The branch never touched the removed kind; its migration must still find the kind's previous version."""
    lock.initialize_lock(local_only=True)
    await load_schema(db=db, schema=SchemaRoot(nodes=[_widget(), _gadget()]), update_db=True)

    branch = await create_branch(db=db, branch_name="dest-removed-a-kind")
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=branch)
    await widget.new(db=db, name="widget-on-branch", code="w1")
    await widget.save(db=db)

    await apply_schema_update(db=db, schema=SchemaRoot(nodes=[_gadget(state=HashableModelState.ABSENT)]))
    assert not registry.schema.get_schema_branch(name=default_branch.name).has(name=GADGET_KIND)

    await _merge(db=db, dependency_provider=dependency_provider, default_branch=default_branch, branch=branch)

    assert not registry.schema.get_schema_branch(name=default_branch.name).has(name=GADGET_KIND)
    merged_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    assert not merged_schema.has(name=GADGET_KIND)
    widgets = await NodeManager.query(db=db, schema=WIDGET_KIND, branch=default_branch)
    assert [str(node.get_attribute("name").value) for node in widgets] == ["widget-on-branch"]


async def test_a_destination_rename_reaches_the_rows_the_merge_lands(
    db: InfrahubDatabase,
    default_branch: Branch,
    workflow_awaited_only: WorkflowAwaitedOnly,
    dependency_provider: Provider,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A row created on the branch under the old attribute name is renamed when it reaches the destination.

    The destination's own rows were renamed when it loaded the change; the branch's rows only meet
    that change at merge time, so the merge has to run the rename over them.
    """
    lock.initialize_lock(local_only=True)
    await load_schema(db=db, schema=SchemaRoot(nodes=[_widget()]), update_db=True)

    branch = await create_branch(db=db, branch_name="dest-renamed-an-attribute")
    widget = await Node.init(db=db, schema=WIDGET_KIND, branch=branch)
    await widget.new(db=db, name="widget-on-branch", code="w1")
    await widget.save(db=db)

    code_id = registry.schema.get_node_schema(name=WIDGET_KIND, branch=default_branch).get_attribute(name="code").id
    await apply_schema_update(db=db, schema=SchemaRoot(nodes=[_widget(code_name="identifier", code_id=code_id)]))
    main_widget_schema = registry.schema.get_node_schema(name=WIDGET_KIND, branch=default_branch)
    assert {attr.name for attr in main_widget_schema.attributes} == {"name", "identifier"}

    await _merge(db=db, dependency_provider=dependency_provider, default_branch=default_branch, branch=branch)

    merged_widget = await NodeManager.get_one(db=db, id=widget.id, branch=default_branch, raise_on_error=True)
    assert merged_widget.get_attribute("identifier").value == "w1"
