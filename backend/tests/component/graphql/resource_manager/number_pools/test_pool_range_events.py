from dataclasses import dataclass, field
from typing import Any

import pytest

from infrahub.auth.session import AccountSession
from infrahub.core.branch import Branch
from infrahub.core.changelog.models import RelationshipCardinalityManyChangelog
from infrahub.core.constants import InfrahubKind
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.events.models import InfrahubEvent
from infrahub.events.node_action import NodeCreatedEvent, NodeDeletedEvent, NodeMutatedEvent, NodeUpdatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from tests.adapters.event import MemoryInfrahubEvent
from tests.helpers.graphql import graphql
from tests.helpers.number_pool import add_pool_range, create_range_only_pool
from tests.helpers.schema import TICKET, load_schema

from .helpers import bounds_input, create_pool, range_details, ticket_pool_input

CREATE_POOL = """
mutation CreatePool($data: CoreNumberPoolCreateInput!) {
  CoreNumberPoolCreate(data: $data) {
    object { id }
  }
}
"""

UPDATE_POOL = """
mutation UpdatePool($data: CoreNumberPoolUpdateInput!) {
  CoreNumberPoolUpdate(data: $data) {
    ok
  }
}
"""

UPSERT_POOL = """
mutation UpsertPool($data: CoreNumberPoolUpsertInput!) {
  CoreNumberPoolUpsert(data: $data) {
    ok
  }
}
"""

DELETE_POOL = """
mutation DeletePool($data: DeleteInput!) {
  CoreNumberPoolDelete(data: $data) {
    ok
  }
}
"""

POOL = "pool"
EVENT_ACTIONS: dict[type[NodeMutatedEvent], str] = {
    NodeCreatedEvent: "created",
    NodeUpdatedEvent: "updated",
    NodeDeletedEvent: "deleted",
}
SUMMARIZED_POOL_ATTRIBUTES = ("name", "start_range", "end_range")
CREATED_POOL_FIELDS = (
    "allocation_scope",
    "description",
    "display_label",
    "end_range",
    "human_friendly_id",
    "name",
    "node",
    "node_attribute",
    "pool_type",
    "ranges",
    "start_range",
)
CREATED_RANGE_FIELDS = ("allocation_weight", "display_label", "end", "human_friendly_id", "pool", "start")
DELETED_RANGE_FIELDS = ("display_label", "end", "pool", "start")


@dataclass(frozen=True)
class SummarizedEvent:
    """A node event with its node, its parent event's node and its range peers named by label instead of id."""

    action: str
    node: str
    fields: tuple[str, ...]
    parent: str | None = None
    attributes: dict[str, tuple[Any, Any]] = field(default_factory=dict)
    """The previous and the new value of each pool attribute the event lists, among name, start_range and end_range."""
    ranges: dict[str, str] = field(default_factory=dict)
    """The change listed for each peer of the pool `ranges` relationship."""


def _created_range(label: str) -> SummarizedEvent:
    return SummarizedEvent(action="created", node=label, fields=CREATED_RANGE_FIELDS, parent=POOL)


def _deleted_range(label: str) -> SummarizedEvent:
    return SummarizedEvent(action="deleted", node=label, fields=DELETED_RANGE_FIELDS, parent=POOL)


@pytest.fixture
async def ticket_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[TICKET]))
    default_branch.update_schema_hash()


async def _execute_with_events(
    db: InfrahubDatabase,
    branch: Branch,
    session: AccountSession,
    source: str,
    variables: dict[str, Any],
) -> tuple[dict[str, Any], list[InfrahubEvent]]:
    memory_event = MemoryInfrahubEvent()
    service = await InfrahubServices.new(event=memory_event)
    gql_params = await prepare_graphql_params(db=db, branch=branch, service=service, account_session=session)
    result = await graphql(
        schema=gql_params.schema,
        source=source,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )
    assert not result.errors
    assert result.data
    assert gql_params.context.background
    await gql_params.context.background()
    return result.data, memory_event.events


async def _range_labels(db: InfrahubDatabase, pool_id: str) -> dict[str, str]:
    return {range_id: f"range {start}-{end}" for range_id, start, end, _ in await range_details(db=db, pool_id=pool_id)}


def _pool_and_range_events(events: list[InfrahubEvent]) -> list[NodeMutatedEvent]:
    return [
        event
        for event in events
        if isinstance(event, NodeMutatedEvent) and event.kind in {InfrahubKind.NUMBERPOOL, InfrahubKind.NUMBERPOOLRANGE}
    ]


def _summarize(events: list[InfrahubEvent], labels: dict[str, str]) -> list[SummarizedEvent]:
    """Summarize the pool and range events, the pool events first and the range events sorted by label."""
    node_events = _pool_and_range_events(events=events)
    node_labels_by_event_id = {event.meta.id: labels[event.node_id] for event in node_events}
    summaries = []
    for event in node_events:
        attributes: dict[str, tuple[Any, Any]] = {}
        ranges: dict[str, str] = {}
        if event.kind == InfrahubKind.NUMBERPOOL:
            attributes = {
                name: (attribute.value_previous, attribute.value)
                for name, attribute in event.changelog.attributes.items()
                if name in SUMMARIZED_POOL_ATTRIBUTES
            }
            range_changelog = event.changelog.relationships.get("ranges")
            if isinstance(range_changelog, RelationshipCardinalityManyChangelog):
                ranges = {labels[peer.peer_id]: peer.peer_status.value for peer in range_changelog.peers}
        summaries.append(
            SummarizedEvent(
                action=EVENT_ACTIONS[type(event)],
                node=labels[event.node_id],
                fields=tuple(sorted(event.fields)),
                parent=node_labels_by_event_id[event.meta.parent] if event.meta.parent else None,
                attributes=attributes,
                ranges=ranges,
            )
        )
    return sorted(summaries, key=lambda summary: (summary.node != POOL, summary.node))


@dataclass
class PoolCreationCase:
    name: str
    bounds: dict[str, Any]
    expected: list[SummarizedEvent]


POOL_CREATION_CASES: list[PoolCreationCase] = [
    PoolCreationCase(
        name="shorthand",
        bounds=bounds_input(start=1, end=9),
        expected=[
            SummarizedEvent(
                action="created",
                node=POOL,
                fields=CREATED_POOL_FIELDS,
                attributes={"name": (None, "events"), "start_range": (None, 1), "end_range": (None, 9)},
                ranges={"range 1-9": "added"},
            ),
            _created_range("range 1-9"),
        ],
    ),
    PoolCreationCase(
        name="single_range",
        bounds={"ranges": [{"start": 1, "end": 9}]},
        expected=[
            SummarizedEvent(
                action="created",
                node=POOL,
                fields=CREATED_POOL_FIELDS,
                attributes={"name": (None, "events"), "start_range": (None, 1), "end_range": (None, 9)},
                ranges={"range 1-9": "added"},
            ),
            _created_range("range 1-9"),
        ],
    ),
    PoolCreationCase(
        name="two_ranges",
        bounds={"ranges": [{"start": 1, "end": 9}, {"start": 20, "end": 30}]},
        expected=[
            SummarizedEvent(
                action="created",
                node=POOL,
                fields=CREATED_POOL_FIELDS,
                attributes={"name": (None, "events"), "start_range": (None, None), "end_range": (None, None)},
                ranges={"range 1-9": "added", "range 20-30": "added"},
            ),
            _created_range("range 1-9"),
            _created_range("range 20-30"),
        ],
    ),
]


@pytest.mark.parametrize("case", POOL_CREATION_CASES, ids=lambda case: case.name)
async def test_pool_creation_events(
    db: InfrahubDatabase,
    default_branch: Branch,
    ticket_schema: None,
    default_permission_backend: None,
    session_admin: AccountSession,
    case: PoolCreationCase,
) -> None:
    data, events = await _execute_with_events(
        db=db,
        branch=default_branch,
        session=session_admin,
        source=CREATE_POOL,
        variables={"data": ticket_pool_input(name="events", bounds=case.bounds)},
    )
    pool_id = data["CoreNumberPoolCreate"]["object"]["id"]
    labels = {pool_id: POOL} | await _range_labels(db=db, pool_id=pool_id)

    assert _summarize(events=events, labels=labels) == case.expected

    (pool_event,) = [event for event in _pool_and_range_events(events=events) if event.node_id == pool_id]
    assert {name: set(pool_event.changelog.attributes[name].properties) for name in SUMMARIZED_POOL_ATTRIBUTES} == {
        name: {"is_protected"} for name in SUMMARIZED_POOL_ATTRIBUTES
    }


@dataclass
class PoolWriteCase:
    name: str
    source: str
    initial_ranges: list[tuple[int, int]]
    data: dict[str, Any]
    expected: list[SummarizedEvent]
    created_with_shorthand: bool = False
    """The pool is created through the API with `start_range` 1 and `end_range` 9 instead of with `initial_ranges`."""


POOL_WRITE_CASES: list[PoolWriteCase] = [
    PoolWriteCase(
        name="rename_and_add_a_range",
        source=UPDATE_POOL,
        initial_ranges=[(1, 10)],
        data={"name": {"value": "renamed"}, "ranges": [{"start": 1, "end": 10}, {"start": 20, "end": 30}]},
        expected=[
            SummarizedEvent(
                action="updated",
                node=POOL,
                fields=("display_label", "human_friendly_id", "name", "ranges"),
                attributes={"name": ("ranged", "renamed")},
                ranges={"range 20-30": "added"},
            ),
            _created_range("range 20-30"),
        ],
    ),
    PoolWriteCase(
        name="replace_two_ranges_by_one",
        source=UPDATE_POOL,
        initial_ranges=[(1, 10), (20, 30)],
        data={"ranges": [{"start": 1, "end": 15}]},
        expected=[
            SummarizedEvent(
                action="updated",
                node=POOL,
                fields=("end_range", "ranges", "start_range"),
                attributes={"start_range": (None, 1), "end_range": (None, 15)},
                ranges={"range 1-10": "removed", "range 20-30": "removed", "range 1-15": "added"},
            ),
            _deleted_range("range 1-10"),
            _created_range("range 1-15"),
            _deleted_range("range 20-30"),
        ],
    ),
    PoolWriteCase(
        name="keep_reweight_remove_and_add_ranges",
        source=UPDATE_POOL,
        initial_ranges=[(1, 10), (20, 30), (40, 50)],
        data={
            "ranges": [
                {"start": 1, "end": 10},
                {"start": 20, "end": 30, "allocation_weight": 5},
                {"start": 60, "end": 70},
            ]
        },
        expected=[
            SummarizedEvent(
                action="updated",
                node=POOL,
                fields=("ranges",),
                ranges={"range 40-50": "removed", "range 60-70": "added"},
            ),
            SummarizedEvent(action="updated", node="range 20-30", fields=("allocation_weight",), parent=POOL),
            _deleted_range("range 40-50"),
            _created_range("range 60-70"),
        ],
    ),
    PoolWriteCase(
        name="reweight_a_range_only",
        source=UPDATE_POOL,
        initial_ranges=[(1, 10), (20, 30)],
        data={"ranges": [{"start": 1, "end": 10}, {"start": 20, "end": 30, "allocation_weight": 5}]},
        expected=[SummarizedEvent(action="updated", node="range 20-30", fields=("allocation_weight",))],
    ),
    PoolWriteCase(
        name="shorthand_rewrites_the_single_range",
        source=UPDATE_POOL,
        initial_ranges=[],
        created_with_shorthand=True,
        data=bounds_input(start=1, end=20),
        expected=[
            SummarizedEvent(action="updated", node=POOL, fields=("end_range",), attributes={"end_range": (9, 20)}),
            SummarizedEvent(action="updated", node="range 1-20", fields=("display_label", "end"), parent=POOL),
        ],
    ),
    PoolWriteCase(
        name="shorthand_on_a_pool_without_range",
        source=UPDATE_POOL,
        initial_ranges=[],
        data=bounds_input(start=1, end=20),
        expected=[
            SummarizedEvent(
                action="updated",
                node=POOL,
                fields=("end_range", "ranges", "start_range"),
                attributes={"start_range": (None, 1), "end_range": (None, 20)},
                ranges={"range 1-20": "added"},
            ),
            _created_range("range 1-20"),
        ],
    ),
    PoolWriteCase(
        name="upsert_adds_a_range",
        source=UPSERT_POOL,
        initial_ranges=[(1, 10)],
        data=ticket_pool_input(name="ranged", bounds={"ranges": [{"start": 1, "end": 10}, {"start": 20, "end": 30}]}),
        expected=[
            SummarizedEvent(action="updated", node=POOL, fields=("ranges",), ranges={"range 20-30": "added"}),
            _created_range("range 20-30"),
        ],
    ),
]


@pytest.mark.parametrize("case", POOL_WRITE_CASES, ids=lambda case: case.name)
async def test_pool_write_events(
    db: InfrahubDatabase,
    default_branch: Branch,
    ticket_schema: None,
    default_permission_backend: None,
    session_admin: AccountSession,
    case: PoolWriteCase,
) -> None:
    if case.created_with_shorthand:
        pool_id = await create_pool(db=db, branch=default_branch, name="events", bounds=bounds_input(start=1, end=9))
    else:
        pool = await create_range_only_pool(db=db)
        pool_id = pool.get_id()
        for start, end in case.initial_ranges:
            await add_pool_range(db=db, pool=pool, start=start, end=end)
    labels = {pool_id: POOL} | await _range_labels(db=db, pool_id=pool_id)

    _, events = await _execute_with_events(
        db=db,
        branch=default_branch,
        session=session_admin,
        source=case.source,
        variables={"data": {"id": pool_id} | case.data},
    )
    labels |= await _range_labels(db=db, pool_id=pool_id)

    assert _summarize(events=events, labels=labels) == case.expected


async def test_pool_deletion_events(
    db: InfrahubDatabase,
    default_branch: Branch,
    ticket_schema: None,
    default_permission_backend: None,
    session_admin: AccountSession,
) -> None:
    pool = await create_range_only_pool(db=db)
    for start, end in [(1, 10), (20, 30)]:
        await add_pool_range(db=db, pool=pool, start=start, end=end)
    labels = {pool.get_id(): POOL} | await _range_labels(db=db, pool_id=pool.get_id())

    _, events = await _execute_with_events(
        db=db,
        branch=default_branch,
        session=session_admin,
        source=DELETE_POOL,
        variables={"data": {"id": pool.get_id()}},
    )

    assert _summarize(events=events, labels=labels) == [
        SummarizedEvent(
            action="deleted",
            node=POOL,
            fields=("display_label", "human_friendly_id", "name", "node", "node_attribute", "pool_type", "ranges"),
            attributes={"name": ("ranged", None)},
            ranges={"range 1-10": "removed", "range 20-30": "removed"},
        ),
        SummarizedEvent(action="deleted", node="range 1-10", fields=("display_label", "end", "start"), parent=POOL),
        SummarizedEvent(action="deleted", node="range 20-30", fields=("display_label", "end", "start"), parent=POOL),
    ]
