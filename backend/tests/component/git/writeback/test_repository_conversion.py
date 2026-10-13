from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.convert_object_type import ConversionFieldInput, ConversionFieldValue

from infrahub import lock
from infrahub.core.constants import InfrahubKind
from infrahub.core.convert_object_type.repository_conversion import convert_repository_type
from infrahub.core.convert_object_type.schema_mapping import get_schema_mapping
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreGenericRepository, CoreRepository
from infrahub.core.registry import registry
from infrahub.exceptions import NodeNotFoundError
from infrahub.git.writeback.constants import STATE_LOCK_TTL_SECONDS
from infrahub.git.writeback.models import HeldItem, HeldRegeneration
from infrahub.git.writeback.store import STATE_LOCK_NAMESPACE, WritebackIntentStore
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.repositories.create_repository import RepositoryFinalizer
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workers.dependencies import build_message_bus
from tests.adapters.lock import LockAction
from tests.adapters.message_bus import BusRecorder
from tests.helpers.dependency_override import override_dependency
from tests.helpers.graphql import graphql

from .conftest import DELIVERED_COMMIT, pending_merge

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.message_bus import InfrahubMessage
    from tests.adapters.lock import LockTimeline

    from .conftest import StoreUnderTest

CONVERT_OBJECT_TYPE_MUTATION = """
mutation ConvertObjectType(
    $node_id: String!
    $target_kind: String!
    $fields_mapping: GenericScalar!
) {
    ConvertObjectType(data: {
        node_id: $node_id,
        target_kind: $target_kind,
        fields_mapping: $fields_mapping
    }) {
        ok
        node
    }
}
"""


READ_ONLY_REF = {"ref": ConversionFieldInput(data=ConversionFieldValue(attribute_value="main"))}


async def _convert(
    subject: StoreUnderTest,
    account_session: AccountSession,
    node_id: str,
    target_kind: str,
    mapping: dict[str, ConversionFieldInput],
) -> tuple[list[str], list[InfrahubMessage]]:
    """Run the conversion mutation, and return its error messages and the messages it sent on the bus."""
    recorder = BusRecorder()
    service = await InfrahubServices.new(message_bus=recorder, workflow=WorkflowLocalExecution())
    gql_params = await prepare_graphql_params(
        db=subject.db, branch=subject.branch, service=service, account_session=account_session
    )
    result = await graphql(
        schema=gql_params.schema,
        source=CONVERT_OBJECT_TYPE_MUTATION,
        context_value=gql_params.context,
        root_value=None,
        variable_values={
            "node_id": node_id,
            "target_kind": target_kind,
            "fields_mapping": {name: model.model_dump(mode="json") for name, model in mapping.items()},
        },
    )
    return [error.message for error in result.errors or []], recorder.messages


async def _kind_of(subject: StoreUnderTest, node_id: str) -> str:
    node = await NodeManager.get_one(db=subject.db, id=node_id, branch=subject.branch, raise_on_error=True)
    return node.get_kind()


async def test_conversion_to_read_only_is_refused_while_pushes_are_pending(
    subject: StoreUnderTest, session_admin: AccountSession
) -> None:
    await subject.store.enqueue(repository_id=subject.repository_id, entry=pending_merge("e1"), widen=False)
    before = await subject.read()

    errors, messages = await _convert(
        subject, session_admin, subject.repository_id, InfrahubKind.READONLYREPOSITORY, READ_ONLY_REF
    )

    assert errors == [
        "Repository delivery-repository has pending pushes to its remote; retry or abandon them before you "
        "convert the repository."
    ]
    assert await _kind_of(subject, subject.repository_id) == InfrahubKind.REPOSITORY
    assert await subject.read() == before
    assert messages == []


async def test_conversion_to_read_write_refuses_a_value_for_a_read_only_attribute(
    subject: StoreUnderTest, session_admin: AccountSession
) -> None:
    read_only = await Node.init(db=subject.db, schema=InfrahubKind.READONLYREPOSITORY, branch=subject.branch)
    await read_only.new(
        db=subject.db, name="read-only-repository", location="https://git.example.com/read-only-repository.git"
    )
    await read_only.save(db=subject.db)
    mapping = {
        "delivery_queue": ConversionFieldInput(
            data=ConversionFieldValue(attribute_value={"format": 1, "version": 7, "entries": []})
        )
    }

    errors, messages = await _convert(subject, session_admin, read_only.id, InfrahubKind.REPOSITORY, mapping)

    assert errors == ["A conversion to CoreRepository cannot set the read-only attributes delivery_queue."]
    assert await _kind_of(subject, read_only.id) == InfrahubKind.READONLYREPOSITORY
    assert messages == []


async def test_conversion_to_read_only_is_refused_while_a_regeneration_waits_for_its_release(
    subject: StoreUnderTest, session_admin: AccountSession
) -> None:
    await subject.store.enqueue(repository_id=subject.repository_id, entry=pending_merge("e1"), widen=False)
    await subject.store.hold(
        repository_id=subject.repository_id,
        held=HeldRegeneration(artifact_definitions=(HeldItem(id="artifact-definition-1", hold_seq=0),)),
    )
    snapshot = await subject.store.start_attempt(repository_id=subject.repository_id)
    await subject.store.settle_delivery(
        repository_id=subject.repository_id, snapshot=snapshot, delivered_commit=DELIVERED_COMMIT
    )
    before = await subject.read()
    assert (before.queue.entries, before.held.is_empty) == ((), False)

    errors, messages = await _convert(
        subject, session_admin, subject.repository_id, InfrahubKind.READONLYREPOSITORY, READ_ONLY_REF
    )

    assert errors == [
        "Repository delivery-repository has a regeneration that waits to be released after a push; wait for the "
        "release, then convert the repository."
    ]
    assert await _kind_of(subject, subject.repository_id) == InfrahubKind.REPOSITORY
    assert await subject.read() == before
    assert messages == []


class _RecordedPostCreate(RepositoryFinalizer):
    """Records the converted repository instead of checking its remote through a worker, which this test has not."""

    def __init__(self) -> None:
        self.created: list[str] = []

    async def post_create(
        self,
        obj: CoreGenericRepository,
        branch: Branch,
        db: InfrahubDatabase,
        delete_on_connectivity_failure: bool = True,
    ) -> None:
        self.created.append(obj.id)


async def _wait_until_queued(timeline: LockTimeline, lock_name: str, count: int) -> None:
    async def queued() -> None:
        while timeline.waiting(lock_name) != count:  # noqa: ASYNC110
            await asyncio.sleep(0.05)

    await asyncio.wait_for(queued(), timeout=60)


async def test_merge_queued_during_a_conversion_waits_for_it_and_fails_on_the_deleted_repository(
    subject: StoreUnderTest, recording_lock_timeline: LockTimeline, dependency_provider: Provider
) -> None:
    state_lock_name = f"{STATE_LOCK_NAMESPACE}.{subject.repository_id}"
    state_lock = lock.registry.get(
        name=subject.repository_id, namespace=STATE_LOCK_NAMESPACE, ttl=STATE_LOCK_TTL_SECONDS
    )
    repository = await NodeManager.get_one(
        db=subject.db,
        id=subject.repository_id,
        kind=CoreRepository,
        branch=subject.branch,
        raise_on_error=True,
    )
    source_schema = registry.get_node_schema(name=InfrahubKind.REPOSITORY, branch=subject.branch)
    target_schema = registry.get_node_schema(name=InfrahubKind.READONLYREPOSITORY, branch=subject.branch)
    mapping = {
        name: ConversionFieldInput(source_field=field.source_field_name)
        for name, field in get_schema_mapping(source_schema=source_schema, target_schema=target_schema).items()
        if field.source_field_name is not None
    } | READ_ONLY_REF
    post_create = _RecordedPostCreate()
    held = asyncio.Event()
    release = asyncio.Event()

    async def hold_the_state_lock() -> None:
        async with state_lock:
            held.set()
            await release.wait()

    bus = BusRecorder()

    with override_dependency(build_message_bus, lambda: bus, dependency_provider=dependency_provider):
        holder = asyncio.create_task(hold_the_state_lock())
        await asyncio.wait_for(held.wait(), timeout=60)
        conversion = asyncio.create_task(
            convert_repository_type(
                repository=repository,
                target_schema=target_schema,
                mapping=mapping,
                branch=subject.branch,
                db=subject.db,
                repository_post_creator=post_create,
                delivery_state=WritebackIntentStore(
                    db=subject.db, lock_registry=lock.registry, default_branch=subject.branch, clock=subject.clock
                ),
            )
        )
        await _wait_until_queued(recording_lock_timeline, state_lock_name, count=1)
        async with subject.db.start_session() as merge_db:
            merge_store = WritebackIntentStore(
                db=merge_db, lock_registry=lock.registry, default_branch=subject.branch, clock=subject.clock
            )
            enqueue = asyncio.create_task(
                merge_store.enqueue(repository_id=subject.repository_id, entry=pending_merge("e1"), widen=False)
            )
            await _wait_until_queued(recording_lock_timeline, state_lock_name, count=2)
            release.set()
            await holder
            converted = await conversion
            with pytest.raises(NodeNotFoundError):
                await enqueue

    assert (converted.get_kind(), post_create.created) == (InfrahubKind.READONLYREPOSITORY, [converted.id])
    assert await NodeManager.get_one(db=subject.db, id=subject.repository_id, branch=subject.branch) is None
    assert [event.action for event in recording_lock_timeline.events if event.name == state_lock_name] == [
        LockAction.WAIT,
        LockAction.ACQUIRE,
        LockAction.WAIT,
        LockAction.WAIT,
        LockAction.RELEASE,
        LockAction.ACQUIRE,
        LockAction.RELEASE,
        LockAction.ACQUIRE,
        LockAction.RELEASE,
    ]
