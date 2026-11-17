from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.components import ComponentType
from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.schema_change.constants import SCHEMA_CHANGE_HISTORY_MAX_LIMIT, SCHEMA_CHANGE_OPERATIONS_MAX_LIMIT
from infrahub.core.schema_change.enums import (
    SchemaChangeApplicationStatus,
    SchemaChangeStatus,
    SchemaOperationSection,
    SchemaOperationType,
)
from infrahub.core.schema_change.history_reader import SchemaChangeHistoryReader
from infrahub.core.schema_change.operations import SchemaOperation
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.services.component import InfrahubComponent
from tests.adapters.cache import MemoryCache
from tests.adapters.event import MemoryInfrahubEvent
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from graphql import ExecutionResult
    from pydantic import JsonValue

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    MutationRunner = Callable[[str, dict[str, str]], Awaitable[ExecutionResult]]

KIND = "TestChoice"
DROPDOWN_ATTRIBUTE = "temperature_scale"
ENUM_ATTRIBUTE = "status"
DROPDOWN_IN_USE = "celsius"
DROPDOWN_ADDED = "fahrenheit"
ENUM_IN_USE = "passive"
ENUM_ADDED = "standby"

CELSIUS: dict[str, JsonValue] = {
    "id": None,
    "state": "present",
    "name": "celsius",
    "description": "",
    "color": "#ed6a5a",
    "label": "Celsius",
}
FAHRENHEIT_INPUT: dict[str, JsonValue] = {
    "id": None,
    "state": "present",
    "name": "fahrenheit",
    "description": None,
    "color": None,
    "label": "Fahrenheit",
}
FAHRENHEIT_SAVED: dict[str, JsonValue] = {
    "id": None,
    "state": "present",
    "name": "fahrenheit",
    "description": "",
    "color": "#f4f1bb",
    "label": "Fahrenheit",
}

DROPDOWN_ADD = """
mutation($dropdown: String!) {
    SchemaDropdownAdd(data: {kind: "TestChoice", attribute: "temperature_scale", dropdown: $dropdown, label: "Fahrenheit"}) {
        ok
    }
}
"""
DROPDOWN_REMOVE = """
mutation($dropdown: String!) {
    SchemaDropdownRemove(data: {kind: "TestChoice", attribute: "temperature_scale", dropdown: $dropdown}) {
        ok
    }
}
"""
ENUM_ADD = """
mutation($enum: String!) {
    SchemaEnumAdd(data: {kind: "TestChoice", attribute: "status", enum: $enum}) {
        ok
    }
}
"""
ENUM_REMOVE = """
mutation($enum: String!) {
    SchemaEnumRemove(data: {kind: "TestChoice", attribute: "status", enum: $enum}) {
        ok
    }
}
"""


@dataclass(frozen=True)
class StoredSchemaChange:
    """One schema change of the history with what this test checks of it."""

    id: str
    status: SchemaChangeStatus
    version: int | None
    parent_id: str | None
    applied_at: str | None
    operations: list[SchemaOperation]
    applications: list[tuple[SchemaChangeApplicationStatus, str, int]]
    """The status, the timestamp and the number of migration records of each application."""


async def _read_history(db: InfrahubDatabase, branch: str) -> list[StoredSchemaChange]:
    reader = SchemaChangeHistoryReader(db=db)
    page = await reader.list_schema_changes(branch=branch, limit=SCHEMA_CHANGE_HISTORY_MAX_LIMIT, offset=0)
    ids = [str(entry.schema_change.uuid) for entry in page.entries]
    operations = await reader.list_operations(schema_change_ids=ids, limit=SCHEMA_CHANGE_OPERATIONS_MAX_LIMIT, offset=0)
    applications = await reader.list_applications(schema_change_ids=ids)
    return [
        StoredSchemaChange(
            id=str(entry.schema_change.uuid),
            status=entry.schema_change.status,
            version=entry.schema_change.version,
            parent_id=str(entry.parent.uuid) if entry.parent else None,
            applied_at=entry.schema_change.applied_at,
            operations=[stored.operation for stored in operations[str(entry.schema_change.uuid)].operations],
            applications=[
                (record.application.status, record.application.at, len(record.migrations))
                for record in applications[str(entry.schema_change.uuid)]
            ],
        )
        for entry in page.entries
    ]


def _list_change(attribute: str, property_name: str, value: JsonValue, previous_value: JsonValue) -> SchemaOperation:
    return SchemaOperation(
        operation_type=SchemaOperationType.ELEMENT_PROPERTY,
        kind=KIND,
        section=SchemaOperationSection.ATTRIBUTES,
        element_name=attribute,
        property_name=property_name,
        value=value,
        previous_value=previous_value,
    )


@pytest.fixture(scope="class")
async def node_using_choices(db: InfrahubDatabase, choices_schema_scope_class: None) -> Node:
    node = await Node.init(db=db, schema=KIND)
    await node.new(db=db, name="choice-in-use", status=ENUM_IN_USE, temperature_scale=DROPDOWN_IN_USE)
    await node.save(db=db)
    return node


@pytest.fixture(scope="class")
async def service(db: InfrahubDatabase) -> InfrahubServices:
    cache = MemoryCache()
    bus = BusRecorder()
    return await InfrahubServices.new(
        database=db,
        message_bus=bus,
        cache=cache,
        event=MemoryInfrahubEvent(),
        component_type=ComponentType.API_SERVER,
        component=InfrahubComponent(cache=cache, db=db, message_bus=bus, component_type=ComponentType.API_SERVER),
    )


class TestDropdownAndEnumMutationHistory:
    """Each method continues from the history that the method before it left."""

    @pytest.fixture(scope="class")
    async def run_mutation(
        self,
        db: InfrahubDatabase,
        default_permission_backend_scope_class: None,
        default_branch_scope_class: Branch,
        choices_schema_scope_class: None,
        node_using_choices: Node,
        session_admin_scope_class: AccountSession,
        service: InfrahubServices,
    ) -> MutationRunner:
        async def _run(query: str, variables: dict[str, str]) -> ExecutionResult:
            default_branch_scope_class.update_schema_hash()
            gql_params = await prepare_graphql_params(
                db=db, branch=default_branch_scope_class, account_session=session_admin_scope_class, service=service
            )
            return await graphql(
                schema=gql_params.schema,
                source=query,
                context_value=gql_params.context,
                root_value=None,
                variable_values=variables,
            )

        return _run

    async def test_dropdown_add_stores_the_first_applied_schema_change(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, run_mutation: MutationRunner
    ) -> None:
        result = await run_mutation(DROPDOWN_ADD, {"dropdown": DROPDOWN_ADDED})

        assert result.errors is None
        history = await _read_history(db=db, branch=default_branch_scope_class.name)
        assert len(history) == 1
        (schema_change,) = history
        assert schema_change.applied_at is not None
        assert schema_change == StoredSchemaChange(
            id=schema_change.id,
            status=SchemaChangeStatus.APPLIED,
            version=1,
            parent_id=None,
            applied_at=schema_change.applied_at,
            operations=[
                _list_change(
                    attribute=DROPDOWN_ATTRIBUTE,
                    property_name="choices",
                    value=[CELSIUS, FAHRENHEIT_INPUT],
                    previous_value=[CELSIUS],
                )
            ],
            applications=[(SchemaChangeApplicationStatus.APPLIED, schema_change.applied_at, 0)],
        )

    async def test_dropdown_add_of_an_existing_choice_stores_nothing(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, run_mutation: MutationRunner
    ) -> None:
        history_before = await _read_history(db=db, branch=default_branch_scope_class.name)

        result = await run_mutation(DROPDOWN_ADD, {"dropdown": DROPDOWN_IN_USE})

        assert [error.message for error in result.errors or []] == [
            "The dropdown value celsius already exists on TestChoice in attribute temperature_scale"
        ]
        assert await _read_history(db=db, branch=default_branch_scope_class.name) == history_before

    async def test_dropdown_remove_stores_the_next_version(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, run_mutation: MutationRunner
    ) -> None:
        result = await run_mutation(DROPDOWN_REMOVE, {"dropdown": DROPDOWN_ADDED})

        assert result.errors is None
        history = await _read_history(db=db, branch=default_branch_scope_class.name)
        assert len(history) == 2
        first, second = history
        assert second.applied_at is not None
        assert second == StoredSchemaChange(
            id=second.id,
            status=SchemaChangeStatus.APPLIED,
            version=2,
            parent_id=first.id,
            applied_at=second.applied_at,
            operations=[
                _list_change(
                    attribute=DROPDOWN_ATTRIBUTE,
                    property_name="choices",
                    value=[CELSIUS],
                    previous_value=[FAHRENHEIT_SAVED, CELSIUS],
                )
            ],
            applications=[(SchemaChangeApplicationStatus.APPLIED, second.applied_at, 0)],
        )

    async def test_dropdown_remove_of_a_choice_in_use_stores_nothing(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, run_mutation: MutationRunner
    ) -> None:
        history_before = await _read_history(db=db, branch=default_branch_scope_class.name)

        result = await run_mutation(DROPDOWN_REMOVE, {"dropdown": DROPDOWN_IN_USE})

        assert [error.message for error in result.errors or []] == [
            "There are still TestChoice objects using this dropdown"
        ]
        assert await _read_history(db=db, branch=default_branch_scope_class.name) == history_before

    async def test_enum_add_stores_the_next_version(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, run_mutation: MutationRunner
    ) -> None:
        result = await run_mutation(ENUM_ADD, {"enum": ENUM_ADDED})

        assert result.errors is None
        history = await _read_history(db=db, branch=default_branch_scope_class.name)
        assert len(history) == 3
        third = history[2]
        assert third.applied_at is not None
        assert third == StoredSchemaChange(
            id=third.id,
            status=SchemaChangeStatus.APPLIED,
            version=3,
            parent_id=history[1].id,
            applied_at=third.applied_at,
            operations=[
                _list_change(
                    attribute=ENUM_ATTRIBUTE,
                    property_name="enum",
                    value=["active", "passive", "standby"],
                    previous_value=["active", "passive"],
                )
            ],
            applications=[(SchemaChangeApplicationStatus.APPLIED, third.applied_at, 0)],
        )

    async def test_enum_add_of_an_existing_value_stores_nothing(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, run_mutation: MutationRunner
    ) -> None:
        history_before = await _read_history(db=db, branch=default_branch_scope_class.name)

        result = await run_mutation(ENUM_ADD, {"enum": ENUM_IN_USE})

        assert [error.message for error in result.errors or []] == [
            "The enum value passive already exists on TestChoice in attribute status"
        ]
        assert await _read_history(db=db, branch=default_branch_scope_class.name) == history_before

    async def test_enum_remove_of_a_value_in_use_stores_nothing(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, run_mutation: MutationRunner
    ) -> None:
        history_before = await _read_history(db=db, branch=default_branch_scope_class.name)

        result = await run_mutation(ENUM_REMOVE, {"enum": ENUM_IN_USE})

        assert [error.message for error in result.errors or []] == [
            "There are still TestChoice objects using this enum"
        ]
        assert await _read_history(db=db, branch=default_branch_scope_class.name) == history_before

    async def test_enum_remove_stores_the_next_version(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, run_mutation: MutationRunner
    ) -> None:
        result = await run_mutation(ENUM_REMOVE, {"enum": ENUM_ADDED})

        assert result.errors is None
        history = await _read_history(db=db, branch=default_branch_scope_class.name)
        assert len(history) == 4
        fourth = history[3]
        assert fourth.applied_at is not None
        assert fourth == StoredSchemaChange(
            id=fourth.id,
            status=SchemaChangeStatus.APPLIED,
            version=4,
            parent_id=history[2].id,
            applied_at=fourth.applied_at,
            operations=[
                _list_change(
                    attribute=ENUM_ATTRIBUTE,
                    property_name="enum",
                    value=["active", "passive"],
                    previous_value=["active", "passive", "standby"],
                )
            ],
            applications=[(SchemaChangeApplicationStatus.APPLIED, fourth.applied_at, 0)],
        )

    async def test_applied_at_is_the_timestamp_of_the_schema_save(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch
    ) -> None:
        history = await _read_history(db=db, branch=default_branch_scope_class.name)
        kind_schema = registry.schema.get(name=KIND, branch=default_branch_scope_class.name, duplicate=False)
        attribute_ids = {
            "choices": kind_schema.get_attribute(name=DROPDOWN_ATTRIBUTE).id,
            "enum": kind_schema.get_attribute(name=ENUM_ATTRIBUTE).id,
        }

        saved_values: list[tuple[JsonValue, JsonValue]] = []
        for schema_change in history:
            assert schema_change.applied_at is not None
            (operation,) = schema_change.operations
            assert operation.property_name is not None
            attribute_id = attribute_ids[operation.property_name]
            assert attribute_id is not None
            applied_at = Timestamp(schema_change.applied_at)
            saved_values.append(
                (
                    await _read_stored_list(
                        db=db,
                        branch=default_branch_scope_class,
                        attribute_id=attribute_id,
                        property_name=operation.property_name,
                        at=applied_at.subtract(microseconds=1),
                    ),
                    await _read_stored_list(
                        db=db,
                        branch=default_branch_scope_class,
                        attribute_id=attribute_id,
                        property_name=operation.property_name,
                        at=applied_at,
                    ),
                )
            )

        assert saved_values == [
            (None, [FAHRENHEIT_SAVED, CELSIUS]),
            ([FAHRENHEIT_SAVED, CELSIUS], [CELSIUS]),
            (["active", "passive"], ["active", "passive", "standby"]),
            (["active", "passive", "standby"], ["active", "passive"]),
        ]


async def _read_stored_list(
    db: InfrahubDatabase, branch: Branch, attribute_id: str, property_name: str, at: Timestamp
) -> JsonValue:
    """Return the list property of a stored attribute schema at a time, or None when the attribute was not stored yet."""
    node = await registry.manager.get_one(db=db, id=attribute_id, branch=branch, at=at)
    if node is None:
        return None
    return node.get_attribute(name=property_name).value
