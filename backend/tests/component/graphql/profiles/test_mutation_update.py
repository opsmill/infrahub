from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from structlog.testing import capture_logs

from infrahub.core.changelog.models import RelationshipCardinalityOneChangelog
from infrahub.core.constants import MetadataOptions, RelationshipCardinality, RelationshipKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.events.models import EventBranchContext, EventContext
from infrahub.events.node_action import NodeUpdatedEvent
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.workflows.catalogue import PROFILE_REFRESH_MULTIPLE
from infrahub.workflows.constants import WorkflowTag
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.workflow import ContextRecordingWorkflow, WorkflowRecorder
from tests.helpers.db_query_counter import CountingInfrahubDatabase
from tests.helpers.graphql import graphql
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from collections import Counter

    from graphql import ExecutionResult

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

ROOM = NodeSchema(name="Room", namespace="Test", attributes=[AttributeSchema(name="name", kind="Text", unique=True)])

DEVICE = NodeSchema(
    name="Device",
    namespace="Test",
    generate_template=True,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="description", kind="Text", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="room",
            peer="TestRoom",
            kind=RelationshipKind.GENERIC,
            optional=True,
            cardinality=RelationshipCardinality.ONE,
        )
    ],
)

RACK = NodeSchema(
    name="Rack",
    namespace="Test",
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="room",
            peer="TestRoom",
            kind=RelationshipKind.GENERIC,
            optional=False,
            cardinality=RelationshipCardinality.ONE,
        )
    ],
)

PANEL = NodeSchema(
    name="Panel",
    namespace="Test",
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="rooms",
            peer="TestRoom",
            kind=RelationshipKind.GENERIC,
            optional=False,
            cardinality=RelationshipCardinality.MANY,
        )
    ],
)


@pytest.fixture
async def device_schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[ROOM, DEVICE]), branch_name=default_branch.name)


@pytest.fixture
async def rack_schema(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> None:
    await load_schema(db=db, schema=SchemaRoot(nodes=[ROOM, RACK, PANEL]), branch_name=default_branch.name)


async def _create_node(db: InfrahubDatabase, branch: Branch, kind: str, **data: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


async def _create_with_profiles(
    db: InfrahubDatabase, branch: Branch, account_session: AccountSession, kind: str, payload: str
) -> str:
    """Create a node through the create mutation, so that its required relationships can come from its profiles."""
    gql_params = await prepare_graphql_params(
        db=db,
        branch=branch,
        account_session=account_session,
        service=await InfrahubServices.new(workflow=WorkflowRecorder()),
    )
    result = await graphql(
        schema=gql_params.schema,
        source=f"mutation {{ {kind}Create(data: {{ {payload} }}) {{ object {{ id }} }} }}",
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert result.errors is None
    assert result.data
    return result.data[f"{kind}Create"]["object"]["id"]


async def _update_profile(
    db: InfrahubDatabase, branch: Branch, account_session: AccountSession, kind: str, profile_id: str, payload: str
) -> tuple[ExecutionResult, WorkflowRecorder]:
    workflow = WorkflowRecorder()
    gql_params = await prepare_graphql_params(db=db, branch=branch, account_session=account_session)
    gql_params.context.service = await InfrahubServices.new(workflow=workflow)
    result = await graphql(
        schema=gql_params.schema,
        source=f'mutation {{ {kind}Update(data: {{ id: "{profile_id}", {payload} }}) {{ ok }} }}',
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    return result, workflow


async def _run_mutation(
    db: InfrahubDatabase, branch: Branch, query: str, account_session: AccountSession | None = None
) -> WorkflowRecorder:
    gql_params = await prepare_graphql_params(db=db, branch=branch, account_session=account_session)
    workflow = WorkflowRecorder()
    gql_params.context.service = await InfrahubServices.new(workflow=workflow)
    result = await graphql(
        schema=gql_params.schema, source=query, context_value=gql_params.context, root_value=None, variable_values={}
    )
    assert result.errors is None
    return workflow


@dataclass
class PeerChangeTestCase:
    name: str
    mutation: str
    rel_name: str
    peer_kind: str


PEER_CHANGE_TEST_CASES: list[PeerChangeTestCase] = [
    PeerChangeTestCase(
        name="update_related_nodes", mutation="Update", rel_name="related_nodes", peer_kind="TestDevice"
    ),
    PeerChangeTestCase(
        name="upsert_related_nodes", mutation="Upsert", rel_name="related_nodes", peer_kind="TestDevice"
    ),
    PeerChangeTestCase(
        name="update_related_templates",
        mutation="Update",
        rel_name="related_templates",
        peer_kind="TemplateTestDevice",
    ),
    PeerChangeTestCase(
        name="upsert_related_templates",
        mutation="Upsert",
        rel_name="related_templates",
        peer_kind="TemplateTestDevice",
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in PEER_CHANGE_TEST_CASES])
async def test_profile_update_refreshes_the_added_and_removed_peers(
    db: InfrahubDatabase,
    default_branch: Branch,
    device_schema: None,
    session_admin: AccountSession,
    test_case: PeerChangeTestCase,
) -> None:
    profile = await _create_node(
        db=db, branch=default_branch, kind="ProfileTestDevice", profile_name="profile-1", profile_priority=10
    )
    name_field = "template_name" if test_case.peer_kind.startswith("Template") else "name"
    peers = [
        await _create_node(
            db=db, branch=default_branch, kind=test_case.peer_kind, profiles=profiles, **{name_field: f"peer-{idx}"}
        )
        for idx, profiles in enumerate([[profile], [profile], []])
    ]

    workflow = await _run_mutation(
        db=db,
        branch=default_branch,
        query=f"""
        mutation {{
            ProfileTestDevice{test_case.mutation}(data: {{
                id: "{profile.id}",
                profile_name: {{ value: "profile-1" }},
                {test_case.rel_name}: [{{ id: "{peers[0].id}" }}, {{ id: "{peers[2].id}" }}]
            }}) {{ ok }}
        }}
        """,
        account_session=session_admin,
    )

    profile = await NodeManager.get_one(db=db, branch=default_branch, id=profile.id, raise_on_error=True)
    relationships = await profile.get_relationship(name=test_case.rel_name).get_relationships(db=db)
    assert {rel.peer_id for rel in relationships} == {peers[0].id, peers[2].id}
    event_context = EventContext(
        branch=EventBranchContext(name=default_branch.name, id=str(default_branch.uuid)),
        account_id=session_admin.account_id,
    )
    assert [
        (
            call["workflow"],
            call["parameters"]["branch_name"],
            call["parameters"]["node_ids"],
            call["parameters"]["context"],
            call["tags"],
        )
        for call in workflow.submit_calls
    ] == [
        (
            PROFILE_REFRESH_MULTIPLE,
            default_branch.name,
            sorted([peers[1].id, peers[2].id]),
            event_context,
            [
                WorkflowTag.BRANCH.render(identifier=default_branch.name),
                WorkflowTag.RELATED_NODE.render(identifier=profile.id),
            ],
        )
    ]


async def test_profile_update_succeeds_when_the_refresh_submission_fails(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None, session_admin: AccountSession
) -> None:
    profile = await _create_node(
        db=db, branch=default_branch, kind="ProfileTestDevice", profile_name="profile-1", profile_priority=10
    )
    device = await _create_node(db=db, branch=default_branch, kind="TestDevice", name="device-1")
    events = MemoryInfrahubEvent()
    workflow = ContextRecordingWorkflow()
    workflow.failures.append(RuntimeError(f"{PROFILE_REFRESH_MULTIPLE.name} submission rejected"))
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        service=await InfrahubServices.new(workflow=workflow, event=events),
    )

    with capture_logs() as records:
        result = await graphql(
            schema=gql_params.schema,
            source=f"""
            mutation {{
                ProfileTestDeviceUpdate(data: {{ id: "{profile.id}", related_nodes: [{{ id: "{device.id}" }}] }}) {{
                    ok
                }}
            }}
            """,
            context_value=gql_params.context,
            root_value=None,
            variable_values={},
        )
    assert gql_params.context.background
    await gql_params.context.background()

    assert result.errors is None
    assert result.data == {"ProfileTestDeviceUpdate": {"ok": True}}
    profile = await NodeManager.get_one(db=db, branch=default_branch, id=profile.id, raise_on_error=True)
    relationships = await profile.get_relationship(name="related_nodes").get_relationships(db=db)
    assert [rel.peer_id for rel in relationships] == [device.id]
    assert [(record["log_level"], record["event"]) for record in records if record["log_level"] == "error"] == [
        ("error", f"Failed to submit the profile refresh of the peers of {profile.id}")
    ]
    assert [(type(event), event.node_id) for event in events.events] == [
        (NodeUpdatedEvent, profile.id),
        (NodeUpdatedEvent, device.id),
    ]


async def test_node_update_records_the_relationship_that_a_profile_sets(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None, session_admin: AccountSession
) -> None:
    room = await _create_node(db=db, branch=default_branch, kind="TestRoom", name="room-1")
    profile = await _create_node(
        db=db, branch=default_branch, kind="ProfileTestDevice", profile_name="profile-1", profile_priority=10, room=room
    )
    device = await _create_node(db=db, branch=default_branch, kind="TestDevice", name="device-1")
    events = MemoryInfrahubEvent()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        service=await InfrahubServices.new(workflow=WorkflowRecorder(), event=events),
    )

    result = await graphql(
        schema=gql_params.schema,
        source=f"""
        mutation {{
            TestDeviceUpdate(data: {{ id: "{device.id}", profiles: [{{ id: "{profile.id}" }}] }}) {{ ok }}
        }}
        """,
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert gql_params.context.background
    await gql_params.context.background()

    assert result.errors is None
    device_events = [
        event for event in events.events if isinstance(event, NodeUpdatedEvent) and event.node_id == device.id
    ]
    assert [sorted(event.fields) for event in device_events] == [["profiles", "room"]]
    room_changelog = device_events[0].changelog.relationships["room"]
    assert isinstance(room_changelog, RelationshipCardinalityOneChangelog)
    assert (room_changelog.peer_id, room_changelog.peer_id_previous) == (room.id, None)
    device = await NodeManager.get_one(
        db=db, branch=default_branch, id=device.id, include_metadata=MetadataOptions.SOURCE, raise_on_error=True
    )
    assert [
        (rel.peer_id, rel.is_from_profile)
        for rel in await device.get_relationship(name="room").get_relationships(db=db)
    ] == [(room.id, True)]


async def test_node_update_records_the_relationship_that_the_removed_profile_set(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None, session_admin: AccountSession
) -> None:
    room = await _create_node(db=db, branch=default_branch, kind="TestRoom", name="room-1")
    profile = await _create_node(
        db=db, branch=default_branch, kind="ProfileTestDevice", profile_name="profile-1", profile_priority=10, room=room
    )
    device_id = await _create_with_profiles(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        kind="TestDevice",
        payload=f'name: {{ value: "device-1" }}, profiles: [{{ id: "{profile.id}" }}]',
    )
    events = MemoryInfrahubEvent()
    gql_params = await prepare_graphql_params(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        service=await InfrahubServices.new(workflow=WorkflowRecorder(), event=events),
    )

    result = await graphql(
        schema=gql_params.schema,
        source=f'mutation {{ TestDeviceUpdate(data: {{ id: "{device_id}", profiles: [] }}) {{ ok }} }}',
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )
    assert gql_params.context.background
    await gql_params.context.background()

    assert result.errors is None
    device_events = [
        event for event in events.events if isinstance(event, NodeUpdatedEvent) and event.node_id == device_id
    ]
    assert [sorted(event.fields) for event in device_events] == [["profiles", "room"]]
    room_changelog = device_events[0].changelog.relationships["room"]
    assert isinstance(room_changelog, RelationshipCardinalityOneChangelog)
    assert (room_changelog.peer_id, room_changelog.peer_id_previous) == (None, room.id)
    device = await NodeManager.get_one(db=db, branch=default_branch, id=device_id, raise_on_error=True)
    assert await device.get_relationship(name="room").get_relationships(db=db) == []


@dataclass(frozen=True)
class CountedMutation:
    query_counts: Counter[str]
    row_counts: Counter[str]
    workflow: WorkflowRecorder


async def _rename_profile(
    db: InfrahubDatabase, branch: Branch, mutation: str, profile: Node, new_name: str
) -> CountedMutation:
    counting_db = CountingInfrahubDatabase.from_db(db=db)
    workflow = await _run_mutation(
        db=counting_db,
        branch=branch,
        query=f"""
        mutation {{
            ProfileTestDevice{mutation}(data: {{ id: "{profile.id}", profile_name: {{ value: "{new_name}" }} }}) {{
                ok
            }}
        }}
        """,
    )
    return CountedMutation(query_counts=counting_db.query_counts, row_counts=counting_db.row_counts, workflow=workflow)


@dataclass
class RenameTestCase:
    name: str
    mutation: str


RENAME_TEST_CASES: list[RenameTestCase] = [
    RenameTestCase(name="update", mutation="Update"),
    RenameTestCase(name="upsert", mutation="Upsert"),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RENAME_TEST_CASES])
async def test_profile_update_without_peers_in_payload_does_not_read_them(
    db: InfrahubDatabase, default_branch: Branch, device_schema: None, test_case: RenameTestCase
) -> None:
    profiles: dict[int, Node] = {}
    for linked_nodes in (2, 6):
        profile = await _create_node(
            db=db,
            branch=default_branch,
            kind="ProfileTestDevice",
            profile_name=f"profile-{linked_nodes}",
            profile_priority=10,
        )
        for idx in range(linked_nodes):
            await _create_node(
                db=db, branch=default_branch, kind="TestDevice", name=f"device-{linked_nodes}-{idx}", profiles=[profile]
            )
        profiles[linked_nodes] = profile

    few = await _rename_profile(
        db=db, branch=default_branch, mutation=test_case.mutation, profile=profiles[2], new_name="renamed-2"
    )
    many = await _rename_profile(
        db=db, branch=default_branch, mutation=test_case.mutation, profile=profiles[6], new_name="renamed-6"
    )

    assert many.row_counts == few.row_counts
    assert many.query_counts == few.query_counts
    assert few.workflow.submit_calls == []
    assert many.workflow.submit_calls == []
    renamed = await NodeManager.get_one(db=db, branch=default_branch, id=profiles[6].id, raise_on_error=True)
    assert renamed.profile_name.value == "renamed-6"


async def test_profile_update_refuses_to_clear_a_required_relationship_that_a_node_inherits(
    db: InfrahubDatabase, default_branch: Branch, rack_schema: None, session_admin: AccountSession
) -> None:
    """The refresh flow could not clear the relationship, so the request refuses the change before it commits."""
    room = await _create_node(db=db, branch=default_branch, kind="TestRoom", name="room-1")
    profile = await _create_node(
        db=db, branch=default_branch, kind="ProfileTestRack", profile_name="profile-1", profile_priority=10, room=room
    )
    rack_id = await _create_with_profiles(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        kind="TestRack",
        payload=f'name: {{ value: "rack-1" }}, profiles: [{{ id: "{profile.id}" }}]',
    )

    result, workflow = await _update_profile(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        kind="ProfileTestRack",
        profile_id=profile.id,
        payload="room: null",
    )

    assert result.errors is not None
    assert [error.message for error in result.errors] == [
        f"Cannot remove the peer of relationship 'room' from profile '{profile.id}' because node "
        f"'TestRack(ID: {rack_id})' (ID: {rack_id}) inherits required relationship 'room' from this profile."
    ]
    assert workflow.submit_calls == []
    profile = await NodeManager.get_one(db=db, branch=default_branch, id=profile.id, raise_on_error=True)
    assert [rel.peer_id for rel in await profile.get_relationship(name="room").get_relationships(db=db)] == [room.id]
    rack = await NodeManager.get_one(
        db=db, branch=default_branch, id=rack_id, include_metadata=MetadataOptions.SOURCE, raise_on_error=True
    )
    assert [
        (rel.peer_id, rel.is_from_profile) for rel in await rack.get_relationship(name="room").get_relationships(db=db)
    ] == [(room.id, True)]


async def test_profile_update_refuses_to_clear_a_required_cardinality_many_relationship_that_a_node_inherits(
    db: InfrahubDatabase, default_branch: Branch, rack_schema: None, session_admin: AccountSession
) -> None:
    rooms = [await _create_node(db=db, branch=default_branch, kind="TestRoom", name=f"room-{idx}") for idx in (1, 2)]
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestPanel",
        profile_name="profile-1",
        profile_priority=10,
        rooms=rooms,
    )
    panel_id = await _create_with_profiles(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        kind="TestPanel",
        payload=f'name: {{ value: "panel-1" }}, profiles: [{{ id: "{profile.id}" }}]',
    )

    result, workflow = await _update_profile(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        kind="ProfileTestPanel",
        profile_id=profile.id,
        payload="rooms: []",
    )

    assert result.errors is not None
    assert [error.message for error in result.errors] == [
        f"Cannot remove the peer of relationship 'rooms' from profile '{profile.id}' because node "
        f"'TestPanel(ID: {panel_id})' (ID: {panel_id}) inherits required relationship 'rooms' from this profile."
    ]
    assert workflow.submit_calls == []
    profile = await NodeManager.get_one(db=db, branch=default_branch, id=profile.id, raise_on_error=True)
    assert sorted(
        rel.peer_id for rel in await profile.get_relationship(name="rooms").get_relationships(db=db)
    ) == sorted(room.id for room in rooms)


async def test_profile_update_clears_a_required_relationship_that_no_node_inherits_from_the_profile(
    db: InfrahubDatabase, default_branch: Branch, rack_schema: None, session_admin: AccountSession
) -> None:
    """One rack sets its room itself, and the other takes its room from a profile of higher priority."""
    rooms = [await _create_node(db=db, branch=default_branch, kind="TestRoom", name=f"room-{idx}") for idx in (1, 2, 3)]
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestRack",
        profile_name="profile-1",
        profile_priority=10,
        room=rooms[0],
    )
    preferred_profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestRack",
        profile_name="profile-2",
        profile_priority=5,
        room=rooms[1],
    )
    await _create_with_profiles(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        kind="TestRack",
        payload=f'name: {{ value: "rack-1" }}, room: {{ id: "{rooms[2].id}" }}, profiles: [{{ id: "{profile.id}" }}]',
    )
    await _create_with_profiles(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        kind="TestRack",
        payload=(
            f'name: {{ value: "rack-2" }}, profiles: [{{ id: "{preferred_profile.id}" }}, {{ id: "{profile.id}" }}]'
        ),
    )

    result, _ = await _update_profile(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        kind="ProfileTestRack",
        profile_id=profile.id,
        payload="room: null",
    )

    assert result.errors is None
    profile = await NodeManager.get_one(db=db, branch=default_branch, id=profile.id, raise_on_error=True)
    assert await profile.get_relationship(name="room").get_relationships(db=db) == []


async def test_profile_update_replaces_a_required_relationship_that_a_node_inherits(
    db: InfrahubDatabase, default_branch: Branch, rack_schema: None, session_admin: AccountSession
) -> None:
    rooms = [await _create_node(db=db, branch=default_branch, kind="TestRoom", name=f"room-{idx}") for idx in (1, 2)]
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestRack",
        profile_name="profile-1",
        profile_priority=10,
        room=rooms[0],
    )
    await _create_with_profiles(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        kind="TestRack",
        payload=f'name: {{ value: "rack-1" }}, profiles: [{{ id: "{profile.id}" }}]',
    )

    result, _ = await _update_profile(
        db=db,
        branch=default_branch,
        account_session=session_admin,
        kind="ProfileTestRack",
        profile_id=profile.id,
        payload=f'room: {{ id: "{rooms[1].id}" }}',
    )

    assert result.errors is None
    profile = await NodeManager.get_one(db=db, branch=default_branch, id=profile.id, raise_on_error=True)
    assert [rel.peer_id for rel in await profile.get_relationship(name="room").get_relationships(db=db)] == [
        rooms[1].id
    ]
