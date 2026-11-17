from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.uuidt import UUIDT

from infrahub import config
from infrahub.core.initialization import create_account
from infrahub.core.schema_change.constants import (
    SchemaChangeApplicationStatus,
    SchemaChangeMigrationStatus,
    SchemaChangeStatus,
    SchemaOperationSection,
    SchemaOperationType,
)
from infrahub.core.schema_change.operations import SchemaOperation

from .shared import (
    CARD_KIND,
    INVALID_HUMAN_FRIENDLY_ID,
    POSITION_ATTRIBUTE,
    SERIAL_ATTRIBUTE,
    SERIAL_LABEL,
    SHARED_CARD_NAME,
    SchemaChangeDataset,
    TestSchemaChangeBase,
    read_schema_change_history,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.helpers.test_client import InfrahubTestClient

MAIN_SCHEMA_CHANGE_NAME = "00001_testingslot_add_and_4_more"
"""The base schema load on main: the generic, then the four nodes of the file."""

CARD_SERIAL_SUMMARY = "testingcard_serial_add"
CARD_SERIAL_LABEL_SUMMARY = "testingcard_serial_update"
SLOT_POSITION_SUMMARY = "testingslot_position_add"

ADDED_ATTRIBUTE_DEFAULTS: dict[str, Any] = {
    "state": "present",
    "read_only": False,
    "unique": False,
    "optional": True,
    "ordered": True,
    "allow_override": "any",
    "display": "default",
    "order_weight": 1000,
}

SCHEMA_CHANGES_QUERY = """
query {
  InfrahubSchemaChange {
    count
    edges {
      node {
        id
        name
        summary
        version
        status
        branch
        parent { id name version branch }
      }
    }
  }
}
"""

LAST_SCHEMA_CHANGE_QUERY = """
query {
  InfrahubSchemaChange(limit: 1, offset: 2) {
    edges {
      node {
        name
        operations {
          count
          edges {
            node {
              position
              operation_type
              kind
              node_type
              section
              element_name
              property_name
              value
              previous_value
            }
          }
        }
        applications {
          status
          branch
          error
          migrations {
            position
            migration_name
            path
            path_type
            schema_kind
            field_name
            property_name
            status
            errors
          }
        }
      }
    }
  }
}
"""

NAMES_QUERY = """
query {
  InfrahubSchemaChange {
    count
    edges { node { name } }
  }
}
"""


@pytest.fixture
def anonymous_read_access() -> Generator[None]:
    original = config.SETTINGS.main.allow_anonymous_access
    config.SETTINGS.main.allow_anonymous_access = True
    yield
    config.SETTINGS.main.allow_anonymous_access = original


class TestSchemaChangeHistory(TestSchemaChangeBase):
    """Loads schema files on one branch and reads the schema changes that each load stores.

    The methods run in the order they are defined, and each one continues from the schema and the records
    that the method before it left.
    """

    @pytest.fixture(scope="class")
    async def token_without_permission(self, db: InfrahubDatabase, initialize_registry: None) -> str:
        """The API token of an account that belongs to no group, so it holds no permission."""
        token = str(UUIDT())
        await create_account(
            db=db, name="schema-change-reader", password="schema-change-reader-password", token_value=token
        )
        return token

    async def test_step01_load_that_changes_the_schema_stores_an_applied_schema_change(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        schema_change_dataset: SchemaChangeDataset,
        schema_card_serial: dict[str, Any],
    ) -> None:
        response = await client.schema.load(schemas=[schema_card_serial], branch=schema_change_dataset.branch_name)

        assert response.errors == {}
        assert response.schema_updated
        history = await read_schema_change_history(db=db, branch=schema_change_dataset.branch_name)
        assert history.page.count == 1
        [schema_change_id] = history.schema_change_ids
        [entry] = history.page.entries
        assert (entry.schema_change.branch, entry.schema_change.status, entry.schema_change.summary) == (
            schema_change_dataset.branch_name,
            SchemaChangeStatus.APPLIED,
            CARD_SERIAL_SUMMARY,
        )
        operations = history.operations[schema_change_id]
        assert operations.count == 1
        assert [(stored.position, stored.operation) for stored in operations.operations] == [
            (
                0,
                SchemaOperation(
                    operation_type=SchemaOperationType.ELEMENT_ADD,
                    kind=CARD_KIND,
                    section=SchemaOperationSection.ATTRIBUTES,
                    element_name=SERIAL_ATTRIBUTE,
                    value={"name": SERIAL_ATTRIBUTE, "kind": "Text", **ADDED_ATTRIBUTE_DEFAULTS},
                ),
            )
        ]
        assert [
            (
                record.application.status,
                [
                    (migration.migration_name, migration.schema_kind, migration.field_name, migration.status)
                    for migration in record.migrations
                ],
            )
            for record in history.applications[schema_change_id]
        ] == [
            (
                SchemaChangeApplicationStatus.APPLIED,
                [("node.attribute.add", CARD_KIND, SERIAL_ATTRIBUTE, SchemaChangeMigrationStatus.APPLIED)],
            )
        ]

    async def test_step02_loading_the_same_file_again_stores_nothing(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        schema_change_dataset: SchemaChangeDataset,
        schema_card_serial: dict[str, Any],
    ) -> None:
        history_before = await read_schema_change_history(db=db, branch=schema_change_dataset.branch_name)

        response = await client.schema.load(schemas=[schema_card_serial], branch=schema_change_dataset.branch_name)

        assert response.errors == {}
        assert not response.schema_updated
        assert await read_schema_change_history(db=db, branch=schema_change_dataset.branch_name) == history_before
        assert history_before.page.count == 1

    async def test_step03_load_that_only_changes_a_label_stores_an_application_without_migration(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        schema_change_dataset: SchemaChangeDataset,
        schema_card_serial_label: dict[str, Any],
    ) -> None:
        response = await client.schema.load(
            schemas=[schema_card_serial_label], branch=schema_change_dataset.branch_name
        )

        assert response.errors == {}
        assert response.schema_updated
        history = await read_schema_change_history(db=db, branch=schema_change_dataset.branch_name)
        assert history.page.count == 2
        label_change_id = history.schema_change_ids[1]
        assert history.page.entries[1].schema_change.summary == CARD_SERIAL_LABEL_SUMMARY
        assert [(stored.position, stored.operation) for stored in history.operations[label_change_id].operations] == [
            (
                0,
                SchemaOperation(
                    operation_type=SchemaOperationType.ELEMENT_PROPERTY,
                    kind=CARD_KIND,
                    section=SchemaOperationSection.ATTRIBUTES,
                    element_name=SERIAL_ATTRIBUTE,
                    property_name="label",
                    value=SERIAL_LABEL,
                    previous_value="Serial",
                ),
            )
        ]
        assert [(record.application.status, record.migrations) for record in history.applications[label_change_id]] == [
            (SchemaChangeApplicationStatus.APPLIED, [])
        ]

    async def test_step04_load_refused_for_an_invalid_file_stores_nothing(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        schema_change_dataset: SchemaChangeDataset,
        schema_card_invalid_human_friendly_id: dict[str, Any],
    ) -> None:
        history_before = await read_schema_change_history(db=db, branch=schema_change_dataset.branch_name)

        response = await client.schema.load(
            schemas=[schema_card_invalid_human_friendly_id], branch=schema_change_dataset.branch_name
        )

        assert response.errors == {
            "data": None,
            "errors": [
                {
                    "message": (
                        f"{CARD_KIND}.human_friendly_id: {INVALID_HUMAN_FRIENDLY_ID} "
                        f"has too many segments on schema {CARD_KIND}"
                    ),
                    "extensions": {"code": 422},
                }
            ],
        }
        assert await read_schema_change_history(db=db, branch=schema_change_dataset.branch_name) == history_before
        assert history_before.page.count == 2

    async def test_step05_load_refused_for_a_constraint_the_nodes_fail_stores_nothing(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        schema_change_dataset: SchemaChangeDataset,
        schema_card_unique_name: dict[str, Any],
    ) -> None:
        history_before = await read_schema_change_history(db=db, branch=schema_change_dataset.branch_name)

        response = await client.schema.load(schemas=[schema_card_unique_name], branch=schema_change_dataset.branch_name)

        card_ids = sorted(schema_change_dataset.card_ids)
        assert response.errors == {
            "data": None,
            "errors": [
                {
                    "message": ",\n".join(
                        [
                            *(
                                f"Node-level 'uniqueness_constraints' constraint violation on schema '{CARD_KIND}'. "
                                f"Node ({CARD_KIND}(ID: {card_id})) is not compliant. "
                                f"The error relates to field name.value='{SHARED_CARD_NAME}'."
                                for card_id in card_ids
                            ),
                            *(
                                f"Attribute-level 'unique' constraint violation on schema '{CARD_KIND}'. "
                                f"Node ({CARD_KIND}(ID: {card_id})) is not compliant. "
                                f"The error relates to field name='{SHARED_CARD_NAME}'."
                                for card_id in card_ids
                            ),
                        ]
                    ),
                    "extensions": {"code": 422},
                }
            ],
        }
        assert await read_schema_change_history(db=db, branch=schema_change_dataset.branch_name) == history_before
        assert history_before.page.count == 2

    async def test_step06_schema_check_stores_nothing_and_returns_the_diff_of_the_candidate(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        schema_change_dataset: SchemaChangeDataset,
        schema_slot_position: dict[str, Any],
    ) -> None:
        history_before = await read_schema_change_history(db=db, branch=schema_change_dataset.branch_name)

        success, response = await client.schema.check(
            schemas=[schema_slot_position], branch=schema_change_dataset.branch_name
        )

        assert success
        assert response is not None
        added_position = {
            "added": {},
            "changed": {"attributes": {"added": {POSITION_ATTRIBUTE: None}, "changed": {}, "removed": {}}},
            "removed": {},
        }
        assert response["diff"] == {
            "added": {},
            "changed": {"TestingSlot": added_position, "TestingPowerSlot": added_position},
            "removed": {},
        }
        assert await read_schema_change_history(db=db, branch=schema_change_dataset.branch_name) == history_before
        assert history_before.page.count == 2

    async def test_step07_load_that_adds_an_attribute_to_a_generic(
        self,
        client: InfrahubClient,
        schema_change_dataset: SchemaChangeDataset,
        schema_slot_position: dict[str, Any],
    ) -> None:
        response = await client.schema.load(schemas=[schema_slot_position], branch=schema_change_dataset.branch_name)

        assert response.errors == {}
        assert response.schema_updated

    async def test_step08_query_returns_three_applied_schema_changes_after_the_version_of_main(
        self, client: InfrahubClient, schema_change_dataset: SchemaChangeDataset
    ) -> None:
        main_result = await client.execute_graphql(query=SCHEMA_CHANGES_QUERY, branch_name="main")
        branch_result = await client.execute_graphql(
            query=SCHEMA_CHANGES_QUERY, branch_name=schema_change_dataset.branch_name
        )

        main_page = main_result["InfrahubSchemaChange"]
        assert main_page["count"] == 1
        assert [(edge["node"]["version"], edge["node"]["status"]) for edge in main_page["edges"]] == [(1, "APPLIED")]
        branch_page = branch_result["InfrahubSchemaChange"]
        assert branch_page["count"] == 3
        assert [
            (edge["node"]["version"], edge["node"]["status"], edge["node"]["branch"]) for edge in branch_page["edges"]
        ] == [
            (2, "APPLIED", schema_change_dataset.branch_name),
            (3, "APPLIED", schema_change_dataset.branch_name),
            (4, "APPLIED", schema_change_dataset.branch_name),
        ]

    async def test_step09_each_name_starts_with_its_version_in_five_digits(
        self, client: InfrahubClient, schema_change_dataset: SchemaChangeDataset
    ) -> None:
        result = await client.execute_graphql(query=SCHEMA_CHANGES_QUERY, branch_name=schema_change_dataset.branch_name)

        assert [
            (edge["node"]["name"], edge["node"]["summary"]) for edge in result["InfrahubSchemaChange"]["edges"]
        ] == [
            (f"00002_{CARD_SERIAL_SUMMARY}", CARD_SERIAL_SUMMARY),
            (f"00003_{CARD_SERIAL_LABEL_SUMMARY}", CARD_SERIAL_LABEL_SUMMARY),
            (f"00004_{SLOT_POSITION_SUMMARY}", SLOT_POSITION_SUMMARY),
        ]

    async def test_step10_attribute_added_to_a_generic_gives_one_operation_and_the_migrations_that_ran(
        self, client: InfrahubClient, schema_change_dataset: SchemaChangeDataset
    ) -> None:
        result = await client.execute_graphql(
            query=LAST_SCHEMA_CHANGE_QUERY, branch_name=schema_change_dataset.branch_name
        )

        def migration(position: int, kind: str) -> dict[str, Any]:
            return {
                "position": position,
                "migration_name": "node.attribute.add",
                "path": f"schema/{kind}/{POSITION_ATTRIBUTE}",
                "path_type": "ATTRIBUTE",
                "schema_kind": kind,
                "field_name": POSITION_ATTRIBUTE,
                "property_name": None,
                "status": "APPLIED",
                "errors": [],
            }

        assert result["InfrahubSchemaChange"]["edges"] == [
            {
                "node": {
                    "name": f"00004_{SLOT_POSITION_SUMMARY}",
                    "operations": {
                        "count": 1,
                        "edges": [
                            {
                                "node": {
                                    "position": 0,
                                    "operation_type": "ELEMENT_ADD",
                                    "kind": "TestingSlot",
                                    "node_type": None,
                                    "section": "ATTRIBUTES",
                                    "element_name": POSITION_ATTRIBUTE,
                                    "property_name": None,
                                    "value": {"name": POSITION_ATTRIBUTE, "kind": "Number", **ADDED_ATTRIBUTE_DEFAULTS},
                                    "previous_value": None,
                                }
                            }
                        ],
                    },
                    "applications": [
                        {
                            "status": "APPLIED",
                            "branch": schema_change_dataset.branch_name,
                            "error": None,
                            "migrations": [migration(0, "TestingSlot"), migration(1, "TestingPowerSlot")],
                        }
                    ],
                }
            }
        ]

    async def test_step11_each_schema_change_has_the_one_before_as_its_parent(
        self, client: InfrahubClient, schema_change_dataset: SchemaChangeDataset
    ) -> None:
        main_result = await client.execute_graphql(query=SCHEMA_CHANGES_QUERY, branch_name="main")
        branch_result = await client.execute_graphql(
            query=SCHEMA_CHANGES_QUERY, branch_name=schema_change_dataset.branch_name
        )

        [main_edge] = main_result["InfrahubSchemaChange"]["edges"]
        main_change = main_edge["node"]
        assert (main_change["name"], main_change["parent"]) == (MAIN_SCHEMA_CHANGE_NAME, None)
        first, second, third = (edge["node"] for edge in branch_result["InfrahubSchemaChange"]["edges"])
        branch_name = schema_change_dataset.branch_name
        assert [first["parent"], second["parent"], third["parent"]] == [
            {"id": main_change["id"], "name": MAIN_SCHEMA_CHANGE_NAME, "version": 1, "branch": "main"},
            {"id": first["id"], "name": f"00002_{CARD_SERIAL_SUMMARY}", "version": 2, "branch": branch_name},
            {"id": second["id"], "name": f"00003_{CARD_SERIAL_LABEL_SUMMARY}", "version": 3, "branch": branch_name},
        ]

    async def test_step12_query_needs_an_account_and_no_other_permission(
        self,
        test_client: InfrahubTestClient,
        schema_change_dataset: SchemaChangeDataset,
        token_without_permission: str,
        anonymous_read_access: None,
    ) -> None:
        url = f"/graphql/{schema_change_dataset.branch_name}"

        anonymous_response = await test_client.post(url, json={"query": NAMES_QUERY})
        account_response = await test_client.post(
            url, json={"query": NAMES_QUERY}, headers={"X-INFRAHUB-KEY": token_without_permission}
        )

        assert (anonymous_response.status_code, anonymous_response.json()) == (
            401,
            {
                "data": None,
                "errors": [
                    {
                        "message": "Authentication is required to perform this operation",
                        "extensions": {"code": "AUTHENTICATION_REQUIRED", "http_status": 401, "data": {}},
                    }
                ],
            },
        )
        assert (account_response.status_code, account_response.json()) == (
            200,
            {
                "data": {
                    "InfrahubSchemaChange": {
                        "count": 3,
                        "edges": [
                            {"node": {"name": f"00002_{CARD_SERIAL_SUMMARY}"}},
                            {"node": {"name": f"00003_{CARD_SERIAL_LABEL_SUMMARY}"}},
                            {"node": {"name": f"00004_{SLOT_POSITION_SUMMARY}"}},
                        ],
                    }
                }
            },
        )
