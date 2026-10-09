from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.convert_object_type import ConversionFieldInput, ConversionFieldValue

from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.git.writeback.models import HeldItem, HeldRegeneration
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql

from .conftest import DELIVERED_COMMIT, pending_merge

if TYPE_CHECKING:
    from infrahub.auth.session import AccountSession
    from infrahub.message_bus import InfrahubMessage

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
