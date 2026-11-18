from __future__ import annotations

from operator import itemgetter
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from infrahub_sdk.uuidt import UUIDT

import infrahub.core.migrations.schema.tasks as tasks_module
from infrahub import config
from infrahub.core import registry
from infrahub.core.initialization import create_account
from infrahub.core.migrations.schema.node_attribute_add import NodeAttributeAddMigration
from infrahub.core.migrations.shared import MigrationInput, MigrationResult
from infrahub.core.schema_change.enums import (
    SchemaChangeApplicationStatus,
    SchemaChangeMigrationStatus,
    SchemaChangeStatus,
    SchemaOperationSection,
    SchemaOperationType,
)
from infrahub.core.schema_change.operations import SchemaOperation
from tests.helpers.schema_change import count_schema_change_records, read_branch_schema_change_records

from .shared import (
    CARD_KIND,
    HEIGHT_ATTRIBUTE,
    INVALID_HUMAN_FRIENDLY_ID,
    POSITION_ATTRIBUTE,
    POWER_SLOT_KIND,
    SERIAL_ATTRIBUTE,
    SERIAL_LABEL,
    SHARED_CARD_NAME,
    SLOT_KIND,
    SchemaChangeDataset,
    SchemaChangeHistorySnapshot,
    TestSchemaChangeBase,
    read_schema_change_history,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.migrations.query import MigrationBaseQuery
    from infrahub.database import InfrahubDatabase
    from tests.helpers.test_client import InfrahubTestClient

MAIN_SCHEMA_CHANGE_NAME = "00001_testingslot_add_and_4_more"
"""The base schema load on main: the generic, then the four nodes of the file."""

CARD_SERIAL_SUMMARY = "testingcard_serial_add"
CARD_SERIAL_LABEL_SUMMARY = "testingcard_serial_update"
SLOT_POSITION_SUMMARY = "testingslot_position_add"
SLOT_HEIGHT_SUMMARY = "testingslot_height_add"
SLOT_MIGRATION_FAILURE = "The height of 2 slots could not be added"

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
          count
          edges {
            node {
              status
              branch
              error
              migrations {
                count
                edges {
                  node {
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


POWER_SLOTS_QUERY = """
query {
  TestingPowerSlot {
    edges { node { id name { value } position { value } } }
  }
}
"""


def _count_history_records(history: SchemaChangeHistorySnapshot) -> int:
    return (
        len(history.schema_change_ids)
        + sum(page.count for page in history.operations.values())
        + sum(1 + len(record.migrations) for records in history.applications.values() for record in records)
    )


class SlotAttributeAddMigrationThatFails(NodeAttributeAddMigration):
    """Fails on the generic slot, and adds the attribute as usual on any other kind."""

    async def execute(
        self,
        migration_input: MigrationInput,
        branch: Branch,
        queries: Sequence[type[MigrationBaseQuery]] | None = None,
    ) -> MigrationResult:
        if self.schema_path.schema_kind == SLOT_KIND:
            return MigrationResult(errors=[SLOT_MIGRATION_FAILURE])
        return await super().execute(migration_input=migration_input, branch=branch, queries=queries)


@pytest.fixture
def failing_slot_attribute_add_migration() -> Generator[None]:
    original_map = tasks_module.MIGRATION_MAP.copy()
    tasks_module.MIGRATION_MAP["node.attribute.add"] = SlotAttributeAddMigrationThatFails
    yield
    tasks_module.MIGRATION_MAP.clear()
    tasks_module.MIGRATION_MAP.update(original_map)


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

        def migration(kind: str) -> dict[str, Any]:
            return {
                "migration_name": "node.attribute.add",
                "path": f"schema/{kind}/{POSITION_ATTRIBUTE}",
                "path_type": "ATTRIBUTE",
                "schema_kind": kind,
                "field_name": POSITION_ATTRIBUTE,
                "property_name": None,
                "status": "APPLIED",
                "errors": [],
            }

        edges = result["InfrahubSchemaChange"]["edges"]
        migration_pages = [
            application["node"].pop("migrations")
            for edge in edges
            for application in edge["node"]["applications"]["edges"]
        ]
        assert [page["count"] for page in migration_pages] == [2]
        records = [migration["node"] for page in migration_pages for migration in page["edges"]]
        # The schema diff orders the two inheriting kinds by a set of IDs, so their positions differ between processes.
        assert [record["position"] for record in records] == [0, 1]
        assert sorted(
            ({key: value for key, value in record.items() if key != "position"} for record in records),
            key=itemgetter("schema_kind"),
        ) == [migration("TestingPowerSlot"), migration("TestingSlot")]
        assert edges == [
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
                    "applications": {
                        "count": 1,
                        "edges": [
                            {
                                "node": {
                                    "status": "APPLIED",
                                    "branch": schema_change_dataset.branch_name,
                                    "error": None,
                                }
                            }
                        ],
                    },
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

    async def test_step13_load_whose_migration_fails_leaves_the_schema_and_the_data_as_before(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        schema_change_dataset: SchemaChangeDataset,
        schema_slot_height: dict[str, Any],
        failing_slot_attribute_add_migration: None,
    ) -> None:
        branch_name = schema_change_dataset.branch_name
        branch = await registry.get_branch(db=db, branch=branch_name)
        registry_hash_before = registry.schema.get_schema_branch(name=branch_name).get_hash()
        stored_hash_before = (await registry.schema.load_schema_from_db(db=db, branch=branch)).get_hash()
        power_slots_before = await client.execute_graphql(query=POWER_SLOTS_QUERY, branch_name=branch_name)

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.schema.load(schemas=[schema_slot_height], branch=branch_name)

        assert (exc_info.value.response.status_code, exc_info.value.response.json()) == (
            502,
            {"data": None, "errors": [{"message": SLOT_MIGRATION_FAILURE, "extensions": {"code": 502}}]},
        )
        assert registry.schema.get_schema_branch(name=branch_name).get_hash() == registry_hash_before
        assert (await registry.schema.load_schema_from_db(db=db, branch=branch)).get_hash() == stored_hash_before
        assert await client.execute_graphql(query=POWER_SLOTS_QUERY, branch_name=branch_name) == power_slots_before
        assert len(power_slots_before["TestingPowerSlot"]["edges"]) == 2

    async def test_step14_failed_load_is_stored_as_a_failed_schema_change_with_the_error_of_the_migration(
        self, db: InfrahubDatabase, schema_change_dataset: SchemaChangeDataset
    ) -> None:
        history = await read_schema_change_history(db=db, branch=schema_change_dataset.branch_name)

        assert history.page.count == 4
        failed_entry = history.page.entries[3]
        failed_id = history.schema_change_ids[3]
        assert (
            failed_entry.schema_change.status,
            failed_entry.schema_change.version,
            failed_entry.schema_change.applied_at,
            failed_entry.schema_change.summary,
            failed_entry.parent,
        ) == (SchemaChangeStatus.FAILED, None, None, SLOT_HEIGHT_SUMMARY, None)
        assert [(stored.position, stored.operation) for stored in history.operations[failed_id].operations] == [
            (
                0,
                SchemaOperation(
                    operation_type=SchemaOperationType.ELEMENT_ADD,
                    kind=SLOT_KIND,
                    section=SchemaOperationSection.ATTRIBUTES,
                    element_name=HEIGHT_ATTRIBUTE,
                    value={"name": HEIGHT_ATTRIBUTE, "kind": "Number", **ADDED_ATTRIBUTE_DEFAULTS},
                ),
            )
        ]
        [application] = history.applications[failed_id]
        assert (application.application.status, application.application.error) == (
            SchemaChangeApplicationStatus.FAILED,
            SLOT_MIGRATION_FAILURE,
        )
        assert sorted(
            (
                migration.schema_kind,
                migration.migration_name,
                migration.field_name,
                migration.status,
                list(migration.errors),
            )
            for migration in application.migrations
        ) == [
            (
                POWER_SLOT_KIND,
                "node.attribute.add",
                HEIGHT_ATTRIBUTE,
                SchemaChangeMigrationStatus.ROLLED_BACK,
                [],
            ),
            (
                SLOT_KIND,
                "node.attribute.add",
                HEIGHT_ATTRIBUTE,
                SchemaChangeMigrationStatus.FAILED,
                [SLOT_MIGRATION_FAILURE],
            ),
        ]

    async def test_step15_query_lists_the_applied_schema_changes_by_version_then_the_failed_one(
        self, client: InfrahubClient, schema_change_dataset: SchemaChangeDataset
    ) -> None:
        result = await client.execute_graphql(query=SCHEMA_CHANGES_QUERY, branch_name=schema_change_dataset.branch_name)

        page = result["InfrahubSchemaChange"]
        assert page["count"] == 4
        assert [
            (edge["node"]["name"], edge["node"]["version"], edge["node"]["status"], edge["node"]["parent"] is None)
            for edge in page["edges"]
        ] == [
            (f"00002_{CARD_SERIAL_SUMMARY}", 2, "APPLIED", False),
            (f"00003_{CARD_SERIAL_LABEL_SUMMARY}", 3, "APPLIED", False),
            (f"00004_{SLOT_POSITION_SUMMARY}", 4, "APPLIED", False),
            (SLOT_HEIGHT_SUMMARY, None, "FAILED", True),
        ]

    async def test_step16_corrected_load_gets_the_next_version_with_the_last_applied_as_parent(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        schema_change_dataset: SchemaChangeDataset,
        schema_slot_height: dict[str, Any],
    ) -> None:
        branch_name = schema_change_dataset.branch_name

        response = await client.schema.load(schemas=[schema_slot_height], branch=branch_name)

        assert response.errors == {}
        assert response.schema_updated
        history = await read_schema_change_history(db=db, branch=branch_name)
        assert history.page.count == 5
        last_applied_id = history.schema_change_ids[2]
        corrected = history.page.entries[3]
        assert (
            corrected.schema_change.status,
            corrected.schema_change.version,
            corrected.schema_change.summary,
            str(corrected.parent.uuid) if corrected.parent else None,
        ) == (SchemaChangeStatus.APPLIED, 5, SLOT_HEIGHT_SUMMARY, last_applied_id)
        assert [
            (record.application.status, [migration.status for migration in record.migrations])
            for record in history.applications[history.schema_change_ids[3]]
        ] == [
            (
                SchemaChangeApplicationStatus.APPLIED,
                [SchemaChangeMigrationStatus.APPLIED, SchemaChangeMigrationStatus.APPLIED],
            )
        ]

    async def test_step17_failed_schema_change_is_still_listed_after_the_corrected_load(
        self, client: InfrahubClient, schema_change_dataset: SchemaChangeDataset
    ) -> None:
        result = await client.execute_graphql(query=SCHEMA_CHANGES_QUERY, branch_name=schema_change_dataset.branch_name)

        page = result["InfrahubSchemaChange"]
        assert page["count"] == 5
        assert [(edge["node"]["name"], edge["node"]["version"], edge["node"]["status"]) for edge in page["edges"]] == [
            (f"00002_{CARD_SERIAL_SUMMARY}", 2, "APPLIED"),
            (f"00003_{CARD_SERIAL_LABEL_SUMMARY}", 3, "APPLIED"),
            (f"00004_{SLOT_POSITION_SUMMARY}", 4, "APPLIED"),
            (f"00005_{SLOT_HEIGHT_SUMMARY}", 5, "APPLIED"),
            (SLOT_HEIGHT_SUMMARY, None, "FAILED"),
        ]

    async def test_step18_deleting_the_branch_deletes_its_records_including_the_failed_schema_change(
        self, db: InfrahubDatabase, client: InfrahubClient, schema_change_dataset: SchemaChangeDataset
    ) -> None:
        branch_name = schema_change_dataset.branch_name
        branch_history = await read_schema_change_history(db=db, branch=branch_name)
        branch_record_uuids = set(await read_branch_schema_change_records(db=db, branch=branch_name))
        main_history = await read_schema_change_history(db=db, branch="main")
        main_records = await read_branch_schema_change_records(db=db, branch="main")
        assert [entry.schema_change.status for entry in branch_history.page.entries] == [
            SchemaChangeStatus.APPLIED,
            SchemaChangeStatus.APPLIED,
            SchemaChangeStatus.APPLIED,
            SchemaChangeStatus.APPLIED,
            SchemaChangeStatus.FAILED,
        ]
        first_parent = branch_history.page.entries[0].parent
        assert first_parent is not None
        assert str(first_parent.uuid) == main_history.schema_change_ids[0]
        assert len(branch_record_uuids) == _count_history_records(history=branch_history)
        assert await count_schema_change_records(db=db) == len(branch_record_uuids) + len(main_records)

        assert await client.branch.delete(branch_name=branch_name) is True

        assert (await read_schema_change_history(db=db, branch=branch_name)).page.count == 0
        assert await count_schema_change_records(db=db, uuids=sorted(branch_record_uuids)) == 0
        assert await read_schema_change_history(db=db, branch="main") == main_history
        assert await read_branch_schema_change_records(db=db, branch="main") == main_records
        assert await count_schema_change_records(db=db) == len(main_records)

    async def test_step19_query_on_main_returns_the_schema_change_of_main_after_the_deletion(
        self, client: InfrahubClient
    ) -> None:
        result = await client.execute_graphql(query=SCHEMA_CHANGES_QUERY, branch_name="main")

        page = result["InfrahubSchemaChange"]
        assert page["count"] == 1
        assert [
            (
                edge["node"]["name"],
                edge["node"]["version"],
                edge["node"]["status"],
                edge["node"]["branch"],
                edge["node"]["parent"],
            )
            for edge in page["edges"]
        ] == [(MAIN_SCHEMA_CHANGE_NAME, 1, "APPLIED", "main", None)]
