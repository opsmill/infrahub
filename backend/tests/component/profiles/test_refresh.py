from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.manager import NodeManager
from infrahub.core.merge.recompute_coalescing import (
    CoalescedRecomputeBuilder,
    CoalescedRecomputeSubmitter,
    RecomputeChainSubmitter,
)
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.events.constants import NodeMutationOrigin
from infrahub.events.models import EventBranchContext, EventContext
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.exceptions import DatabaseError, ValidationError
from infrahub.profiles.node_applier import ChunkProfilesApplier
from infrahub.profiles.refresh import NodeProfilesRefresher
from infrahub.workflows.catalogue import DISPLAY_LABELS_PROCESS_JINJA2
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.python_target_sources import RecordingPythonTargetResolver
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

ROOM_KIND = "TestRoom"
SERVER_KIND = "TestServer"
PORT_KIND = "TestPort"

ROOM = NodeSchema(
    name="Room",
    namespace="Test",
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)
SERVER = NodeSchema(
    name="Server",
    namespace="Test",
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="role", kind="Text", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="room",
            peer=ROOM_KIND,
            kind=RelationshipKind.ATTRIBUTE,
            optional=True,
            cardinality=RelationshipCardinality.ONE,
        )
    ],
)
PORT = NodeSchema(
    name="Port",
    namespace="Test",
    display_label="{{ name__value }} on {{ server__role__value }}",
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="server",
            peer=SERVER_KIND,
            kind=RelationshipKind.GENERIC,
            optional=False,
            cardinality=RelationshipCardinality.ONE,
        )
    ],
)


@dataclass(frozen=True)
class ServerDataset:
    room_id: str
    server_ids: list[str]
    port_ids: list[str]


@dataclass(frozen=True)
class RefresherDoubles:
    refresher: NodeProfilesRefresher
    events: MemoryInfrahubEvent
    workflow: WorkflowRecorder
    resolver: RecordingPythonTargetResolver


@pytest.fixture
async def server_schema(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[ROOM, SERVER, PORT]), branch_name=default_branch.name)


async def _create(db: InfrahubDatabase, kind: str, **data: object) -> Node:
    node = await Node.init(db=db, schema=kind)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


async def _create_servers(db: InfrahubDatabase, count: int, profile_sets_room: bool = True) -> ServerDataset:
    """Servers linked to one profile that sets their role, and their room if asked, with no profile value applied yet."""
    room = await _create(db=db, kind=ROOM_KIND, name=f"room-{count}")
    profile_values: dict[str, object] = {"role": "role-1"}
    if profile_sets_room:
        profile_values["room"] = room
    profile = await _create(
        db=db, kind=f"Profile{SERVER_KIND}", profile_name=f"profile-{count}", profile_priority=1000, **profile_values
    )
    server_ids = []
    port_ids = []
    for idx in range(count):
        server = await _create(db=db, kind=SERVER_KIND, name=f"server-{count}-{idx}", profiles=[profile])
        port = await _create(db=db, kind=PORT_KIND, name=f"port-{count}-{idx}", server=server)
        server_ids.append(server.id)
        port_ids.append(port.id)
    return ServerDataset(room_id=room.id, server_ids=server_ids, port_ids=port_ids)


def _context(branch: Branch) -> EventContext:
    return EventContext(branch=EventBranchContext(name=branch.name, id=str(branch.uuid)), account_id="account-1")


def _refresher(
    db: InfrahubDatabase,
    branch: Branch,
    applier_class: type[ChunkProfilesApplier] = ChunkProfilesApplier,
    transaction_chunk_size: int = 100,
) -> RefresherDoubles:
    events = MemoryInfrahubEvent()
    workflow = WorkflowRecorder()
    resolver = RecordingPythonTargetResolver(targets=[])
    chain = RecomputeChainSubmitter(
        builder=CoalescedRecomputeBuilder(schema_branch=registry.schema.get_schema_branch(name=branch.name)),
        submitter=CoalescedRecomputeSubmitter(workflow=workflow),
        python_resolver=resolver,
    )
    refresher = NodeProfilesRefresher(
        db=db,
        event_service=events,
        chain=chain,
        applier_class=applier_class,
        transaction_chunk_size=transaction_chunk_size,
    )
    return RefresherDoubles(refresher=refresher, events=events, workflow=workflow, resolver=resolver)


async def _role_and_room(db: InfrahubDatabase, branch: Branch, node_id: str) -> tuple[str | None, str | None]:
    server = await NodeManager.get_one(db=db, id=node_id, branch=branch, raise_on_error=True)
    room = await server.get_relationship(name="room").get_peer(db=db)
    return server.get_attribute(name="role").value, room.id if room else None


async def test_refresh_applies_the_profiles_and_recomputes_their_readers(
    db: InfrahubDatabase, default_branch: Branch, server_schema: None
) -> None:
    dataset = await _create_servers(db=db, count=2)
    doubles = _refresher(db=db, branch=default_branch)

    failed_node_ids = await doubles.refresher.refresh(
        branch=default_branch, node_ids=dataset.server_ids, context=_context(branch=default_branch)
    )

    assert failed_node_ids == []
    assert [await _role_and_room(db=db, branch=default_branch, node_id=node_id) for node_id in dataset.server_ids] == [
        ("role-1", dataset.room_id),
        ("role-1", dataset.room_id),
    ]
    assert [(type(event), event.node_id, event.fields, event.meta.origin) for event in doubles.events.events] == [
        (NodeUpdatedEvent, node_id, ["role", "room"], NodeMutationOrigin.RECOMPUTE) for node_id in dataset.server_ids
    ]
    assert [call.node_ids for call in doubles.resolver.calls] == [tuple(dataset.server_ids)]
    assert [
        (
            call["parameters"]["node_kind"],
            call["parameters"]["target_kind"],
            sorted(call["parameters"]["object_ids"]),
            call["parameters"]["recompute_depth"],
        )
        for call in doubles.workflow.get_submit_calls_for(DISPLAY_LABELS_PROCESS_JINJA2)
    ] == [(SERVER_KIND, PORT_KIND, sorted(dataset.server_ids), 1)]


async def test_refresh_of_unchanged_nodes_sends_no_event_and_no_recompute(
    db: InfrahubDatabase, default_branch: Branch, server_schema: None
) -> None:
    dataset = await _create_servers(db=db, count=2)
    await _refresher(db=db, branch=default_branch).refresher.refresh(
        branch=default_branch, node_ids=dataset.server_ids, context=_context(branch=default_branch)
    )
    doubles = _refresher(db=db, branch=default_branch)

    failed_node_ids = await doubles.refresher.refresh(
        branch=default_branch, node_ids=dataset.server_ids, context=_context(branch=default_branch)
    )

    assert failed_node_ids == []
    assert doubles.events.events == []
    assert doubles.resolver.calls == []
    assert doubles.workflow.submit_calls == []


async def test_refresh_reports_a_relationship_that_a_profile_no_longer_sets(
    db: InfrahubDatabase, default_branch: Branch, server_schema: None
) -> None:
    dataset = await _create_servers(db=db, count=2)
    await _refresher(db=db, branch=default_branch).refresher.refresh(
        branch=default_branch, node_ids=dataset.server_ids, context=_context(branch=default_branch)
    )
    server = await NodeManager.get_one(db=db, id=dataset.server_ids[0], branch=default_branch, raise_on_error=True)
    profile_id = (await server.get_relationship(name="profiles").get_relationships(db=db))[0].peer_id
    profile = await NodeManager.get_one(db=db, id=profile_id, branch=default_branch, raise_on_error=True)
    await profile.get_relationship(name="room").update(db=db, data=None)
    await profile.save(db=db)
    doubles = _refresher(db=db, branch=default_branch)

    failed_node_ids = await doubles.refresher.refresh(
        branch=default_branch, node_ids=dataset.server_ids, context=_context(branch=default_branch)
    )

    assert failed_node_ids == []
    assert [await _role_and_room(db=db, branch=default_branch, node_id=node_id) for node_id in dataset.server_ids] == [
        ("role-1", None),
        ("role-1", None),
    ]
    assert [(event.node_id, event.fields) for event in doubles.events.events] == [
        (node_id, ["room"]) for node_id in dataset.server_ids
    ]


@dataclass
class QueryCountTestCase:
    name: str
    node_count: int
    transaction_chunk_size: int
    expected_reads: int
    """Reads of the nodes and of the profile data: one of each for every transaction chunk."""


QUERY_COUNT_TEST_CASES: list[QueryCountTestCase] = [
    QueryCountTestCase(name="two_nodes_one_chunk", node_count=2, transaction_chunk_size=4, expected_reads=1),
    QueryCountTestCase(name="four_nodes_one_chunk", node_count=4, transaction_chunk_size=4, expected_reads=1),
    QueryCountTestCase(name="six_nodes_two_chunks", node_count=6, transaction_chunk_size=4, expected_reads=2),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in QUERY_COUNT_TEST_CASES])
async def test_refresh_reads_the_nodes_and_the_profile_data_once_per_transaction_chunk(
    db: InfrahubDatabase, default_branch: Branch, server_schema: None, test_case: QueryCountTestCase
) -> None:
    # A profile relationship loads its peer for each node, so only the attribute is set here.
    dataset = await _create_servers(db=db, count=test_case.node_count, profile_sets_room=False)
    counting_db = CountingInfrahubDatabase.from_db(db=db)
    doubles = _refresher(db=counting_db, branch=default_branch, transaction_chunk_size=test_case.transaction_chunk_size)

    failed_node_ids = await doubles.refresher.refresh(
        branch=default_branch, node_ids=dataset.server_ids, context=_context(branch=default_branch)
    )

    assert failed_node_ids == []
    assert len(doubles.events.events) == test_case.node_count
    assert counting_db.count_for("node_list_get_info") == test_case.expected_reads
    assert counting_db.count_for("profile_get_data") == test_case.expected_reads


def _failing_applier(failing_node_id: str, error: Exception) -> type[ChunkProfilesApplier]:
    class FailingProfilesApplier(ChunkProfilesApplier):
        """Raises for one node, after its profile values and relationships are written."""

        async def apply_profiles(self, node: Node) -> list[str]:
            fields = await super().apply_profiles(node=node)
            if node.get_id() == failing_node_id:
                raise error
            return fields

    return FailingProfilesApplier


async def test_refresh_skips_only_the_node_whose_profile_application_raises(
    db: InfrahubDatabase, default_branch: Branch, server_schema: None
) -> None:
    dataset = await _create_servers(db=db, count=3)
    failing_node_id = dataset.server_ids[1]
    doubles = _refresher(
        db=db,
        branch=default_branch,
        applier_class=_failing_applier(
            failing_node_id=failing_node_id, error=ValidationError(f"profiles of {failing_node_id} rejected")
        ),
    )

    failed_node_ids = await doubles.refresher.refresh(
        branch=default_branch, node_ids=dataset.server_ids, context=_context(branch=default_branch)
    )

    assert failed_node_ids == [failing_node_id]
    assert [await _role_and_room(db=db, branch=default_branch, node_id=node_id) for node_id in dataset.server_ids] == [
        ("role-1", dataset.room_id),
        (None, None),
        ("role-1", dataset.room_id),
    ]
    assert [event.node_id for event in doubles.events.events] == [dataset.server_ids[0], dataset.server_ids[2]]


async def test_refresh_recomputes_the_readers_of_committed_chunks_when_a_later_chunk_fails(
    db: InfrahubDatabase, default_branch: Branch, server_schema: None
) -> None:
    dataset = await _create_servers(db=db, count=4)
    doubles = _refresher(
        db=db,
        branch=default_branch,
        applier_class=_failing_applier(
            failing_node_id=dataset.server_ids[2], error=DatabaseError(message="database rejected")
        ),
        transaction_chunk_size=2,
    )

    with pytest.raises(DatabaseError, match=r"^database rejected$"):
        await doubles.refresher.refresh(
            branch=default_branch, node_ids=dataset.server_ids, context=_context(branch=default_branch)
        )

    assert [event.node_id for event in doubles.events.events] == [dataset.server_ids[0], dataset.server_ids[1]]
    assert [
        (
            call["parameters"]["node_kind"],
            call["parameters"]["target_kind"],
            sorted(call["parameters"]["object_ids"]),
            call["parameters"]["recompute_depth"],
        )
        for call in doubles.workflow.get_submit_calls_for(DISPLAY_LABELS_PROCESS_JINJA2)
    ] == [(SERVER_KIND, PORT_KIND, sorted([dataset.server_ids[0], dataset.server_ids[1]]), 1)]


async def test_refresh_reports_a_node_that_does_not_exist(
    db: InfrahubDatabase, default_branch: Branch, server_schema: None
) -> None:
    dataset = await _create_servers(db=db, count=1)
    doubles = _refresher(db=db, branch=default_branch)

    failed_node_ids = await doubles.refresher.refresh(
        branch=default_branch,
        node_ids=["18dab76f-0000-0000-0000-000000000000", dataset.server_ids[0]],
        context=_context(branch=default_branch),
    )

    assert failed_node_ids == ["18dab76f-0000-0000-0000-000000000000"]
    assert await _role_and_room(db=db, branch=default_branch, node_id=dataset.server_ids[0]) == (
        "role-1",
        dataset.room_id,
    )
