"""A proposed change refused by its schema integrity check can be merged once the data is fixed and the checks run again."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.protocols import CoreProposedChange as SdkCoreProposedChange

from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.constants import ValidatorConclusion
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreProposedChange, CoreSchemaCheck, CoreValidator
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.proposed_change.constants import ProposedChangeState
from tests.helpers.constants import PREFECT_EVENT_WAIT_SECONDS
from tests.helpers.test_app import TestInfrahubApp

from ..shared import load_schema

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

SOCKET_KIND = "TestingSocket"
SCHEMA_INTEGRITY_LABEL = "Schema Integrity"

RUN_CHECKS_MUTATION = """
mutation($id: String!) {
    CoreProposedChangeRunCheck(data: { id: $id, check_type: ALL }) {
        ok
    }
}
"""


def _socket_schema() -> SchemaRoot:
    return SchemaRoot(
        version="1.0",
        nodes=[
            NodeSchema(
                name="Socket",
                namespace="Testing",
                include_in_menu=False,
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            )
        ],
    )


async def _schema_integrity_validator(db: InfrahubDatabase, proposed_change_id: str) -> CoreValidator | None:
    proposed_change = await NodeManager.get_one(
        db=db, id=proposed_change_id, kind=CoreProposedChange, raise_on_error=True
    )
    peers = await proposed_change.validations.get_peers(db=db, peer_type=CoreValidator)
    for validator in peers.values():
        if validator.label.value == SCHEMA_INTEGRITY_LABEL:
            return validator
    return None


async def _schema_integrity_conclusion(db: InfrahubDatabase, proposed_change_id: str) -> str | None:
    validator = await _schema_integrity_validator(db=db, proposed_change_id=proposed_change_id)
    return validator.conclusion.value.value if validator else None


async def _wait_for_schema_integrity(db: InfrahubDatabase, proposed_change_id: str, conclusion: str) -> str | None:
    current = None
    for _ in range(PREFECT_EVENT_WAIT_SECONDS):
        current = await _schema_integrity_conclusion(db=db, proposed_change_id=proposed_change_id)
        if current == conclusion:
            return current
        await asyncio.sleep(1)
    return current


async def _schema_integrity_checks(
    db: InfrahubDatabase, proposed_change_id: str
) -> list[tuple[str, dict[Any, Any] | list[Any]]]:
    validator = await _schema_integrity_validator(db=db, proposed_change_id=proposed_change_id)
    assert validator
    checks = await validator.checks.get_peers(db=db, peer_type=CoreSchemaCheck)
    return [(check.conclusion.value.value, check.conflicts.value) for check in checks.values()]


def _failed_check(constraint: str, path: str, node_id: str, message: str) -> tuple[str, dict[Any, Any] | list[Any]]:
    return (
        ValidatorConclusion.FAILURE.value,
        [
            {
                "branch": "placeholder",
                "id": node_id,
                "kind": SOCKET_KIND,
                "name": path,
                "path": path,
                "type": constraint,
                "value": message,
            }
        ],
    )


def _check_sort_key(check: tuple[str, dict[Any, Any] | list[Any]]) -> tuple[str, str]:
    conflicts = check[1]
    assert isinstance(conflicts, list)
    return conflicts[0]["type"], conflicts[0]["id"]


class TestProposedChangeSchemaIntegrityRecheck(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def refused_proposed_change(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> tuple[str, str, str, str]:
        await load_schema(db=db, schema=_socket_schema())
        branch = await client.branch.create(branch_name="socket-on-branch")
        socket = await Node.init(schema=SOCKET_KIND, db=db, branch=branch.name)
        await socket.new(db=db, name="socket-1")
        await socket.save(db=db)
        socket_on_main = await Node.init(schema=SOCKET_KIND, db=db)
        await socket_on_main.new(db=db, name="socket-1")
        await socket_on_main.save(db=db)

        proposed_change = await client.create(
            kind=SdkCoreProposedChange,
            data={"source_branch": branch.name, "destination_branch": "main", "name": "socket-recheck"},
        )
        await proposed_change.save()
        return proposed_change.id, branch.name, socket.id, socket_on_main.id

    async def test_schema_integrity_check_fails_for_a_node_on_the_branch_that_duplicates_a_unique_value_on_main(
        self, db: InfrahubDatabase, refused_proposed_change: tuple[str, str, str, str]
    ) -> None:
        proposed_change_id, _, socket_id, socket_on_main_id = refused_proposed_change

        conclusion = await _wait_for_schema_integrity(
            db=db, proposed_change_id=proposed_change_id, conclusion=ValidatorConclusion.FAILURE.value
        )

        assert conclusion == ValidatorConclusion.FAILURE.value
        checks = await _schema_integrity_checks(db=db, proposed_change_id=proposed_change_id)
        expected = [
            check
            for node_id, label in (
                (socket_id, f"{SOCKET_KIND}(ID: {socket_id})"),
                (socket_on_main_id, f"{SOCKET_KIND}: {socket_on_main_id}"),
            )
            for check in (
                _failed_check(
                    constraint="attribute.unique.update",
                    path=f"schema/{SOCKET_KIND}/name/unique",
                    node_id=node_id,
                    message=f"Attribute-level 'unique' constraint violation on schema '{SOCKET_KIND}'. Node ({label})"
                    " is not compliant. The error relates to field name='socket-1'.",
                ),
                _failed_check(
                    constraint="node.uniqueness_constraints.update",
                    path=f"schema/{SOCKET_KIND}/uniqueness_constraints",
                    node_id=node_id,
                    message=f"Node-level 'uniqueness_constraints' constraint violation on schema '{SOCKET_KIND}'."
                    f" Node ({label}) is not compliant. The error relates to field name.value='socket-1'.",
                ),
            )
        ]
        assert sorted(checks, key=_check_sort_key) == sorted(expected, key=_check_sort_key)

    async def test_merge_is_accepted_after_the_branch_node_is_deleted_and_checks_run_again(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        refused_proposed_change: tuple[str, str, str, str],
    ) -> None:
        proposed_change_id, branch_name, socket_id, _ = refused_proposed_change
        assert (
            await _wait_for_schema_integrity(
                db=db, proposed_change_id=proposed_change_id, conclusion=ValidatorConclusion.FAILURE.value
            )
            == ValidatorConclusion.FAILURE.value
        )
        socket = await NodeManager.get_one(db=db, id=socket_id, branch=branch_name, raise_on_error=True)
        await socket.delete(db=db)

        await client.execute_graphql(query=RUN_CHECKS_MUTATION, variables={"id": proposed_change_id})

        assert (
            await _wait_for_schema_integrity(
                db=db, proposed_change_id=proposed_change_id, conclusion=ValidatorConclusion.SUCCESS.value
            )
            == ValidatorConclusion.SUCCESS.value
        )

        proposed_change = await client.get(kind=SdkCoreProposedChange, id=proposed_change_id)
        proposed_change.state.value = ProposedChangeState.MERGED.value
        await proposed_change.save()

        merged = await client.get(kind=SdkCoreProposedChange, id=proposed_change_id)
        assert merged.state.value == ProposedChangeState.MERGED.value
        stored_branch = await Branch.get_by_name(db=db, name=branch_name)
        assert stored_branch.status == BranchStatus.MERGED
