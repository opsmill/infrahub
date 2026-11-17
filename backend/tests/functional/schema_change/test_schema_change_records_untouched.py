from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.schema import SchemaRoot
from infrahub.core.schema_change.constants import SchemaChangeStatus
from infrahub.core.schema_change.models import SchemaChange
from tests.helpers.schema import load_schema
from tests.helpers.schema_change import (
    StoredSchemaChangeRecord,
    count_schema_change_records,
    read_branch_schema_change_records,
)

from .shared import (
    CARD_KIND,
    POSITION_ATTRIBUTE,
    SCHEMA_FILE_VERSION,
    SERIAL_ATTRIBUTE,
    SLOT_KIND,
    SchemaChangeDataset,
    TestSchemaChangeBase,
    read_schema_change_history,
)

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class SchemaChangeRecordsSnapshot:
    main: dict[str, StoredSchemaChangeRecord]
    branch: dict[str, StoredSchemaChangeRecord]
    nbr_records: int
    """The number of records of every branch, so that a record stored on a third branch is counted too."""


async def take_records_snapshot(db: InfrahubDatabase, branch_name: str) -> SchemaChangeRecordsSnapshot:
    return SchemaChangeRecordsSnapshot(
        main=await read_branch_schema_change_records(db=db, branch="main"),
        branch=await read_branch_schema_change_records(db=db, branch=branch_name),
        nbr_records=await count_schema_change_records(db=db),
    )


def _schema_change_ids(records: dict[str, StoredSchemaChangeRecord]) -> set[str]:
    return {uuid for uuid, record in records.items() if record.label == SchemaChange.get_type()}


class TestSchemaChangeRecordsUntouched(TestSchemaChangeBase):
    """Loads a schema change on main and one on the branch, then rebases and merges the branch.

    The methods run in the order they are defined: the merge comes after the rebase.
    """

    @pytest.fixture(scope="class")
    async def core_schema_in_database(self, db: InfrahubDatabase, initialize_registry: None) -> None:
        """Write the schema of main to the database, because a merge reads the schema of main back from it."""
        await load_schema(db=db, schema=SchemaRoot(version=SCHEMA_FILE_VERSION), update_db=True)

    @pytest.fixture(scope="class")
    async def schema_changes_on_main_and_branch(
        self,
        core_schema_in_database: None,
        client: InfrahubClient,
        schema_change_dataset: SchemaChangeDataset,
        schema_slot_position: dict[str, Any],
        schema_card_serial: dict[str, Any],
    ) -> None:
        main_response = await client.schema.load(schemas=[schema_slot_position])
        assert main_response.errors == {}
        assert main_response.schema_updated

        branch_response = await client.schema.load(
            schemas=[schema_card_serial], branch=schema_change_dataset.branch_name
        )
        assert branch_response.errors == {}
        assert branch_response.schema_updated

    @pytest.fixture(scope="class")
    async def records_before(
        self, db: InfrahubDatabase, schema_change_dataset: SchemaChangeDataset, schema_changes_on_main_and_branch: None
    ) -> SchemaChangeRecordsSnapshot:
        return await take_records_snapshot(db=db, branch_name=schema_change_dataset.branch_name)

    async def test_step01_main_and_the_branch_hold_their_applied_schema_changes(
        self,
        db: InfrahubDatabase,
        schema_change_dataset: SchemaChangeDataset,
        records_before: SchemaChangeRecordsSnapshot,
    ) -> None:
        main_history = await read_schema_change_history(db=db, branch="main")
        branch_history = await read_schema_change_history(db=db, branch=schema_change_dataset.branch_name)

        assert [entry.schema_change.status for entry in main_history.page.entries] == [
            SchemaChangeStatus.APPLIED,
            SchemaChangeStatus.APPLIED,
        ]
        assert [entry.schema_change.status for entry in branch_history.page.entries] == [SchemaChangeStatus.APPLIED]
        assert _schema_change_ids(records_before.main) == set(main_history.schema_change_ids)
        assert _schema_change_ids(records_before.branch) == set(branch_history.schema_change_ids)
        assert records_before.nbr_records == len(records_before.main) + len(records_before.branch)

    async def test_step02_rebase_leaves_the_records_and_their_edges_unchanged(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        schema_change_dataset: SchemaChangeDataset,
        records_before: SchemaChangeRecordsSnapshot,
    ) -> None:
        await client.branch.rebase(branch_name=schema_change_dataset.branch_name)

        slot_schema = await client.schema.get(kind=SLOT_KIND, branch=schema_change_dataset.branch_name, refresh=True)
        assert POSITION_ATTRIBUTE in slot_schema.attribute_names
        assert await take_records_snapshot(db=db, branch_name=schema_change_dataset.branch_name) == records_before

    async def test_step03_merge_leaves_the_records_and_their_edges_unchanged(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        schema_change_dataset: SchemaChangeDataset,
        records_before: SchemaChangeRecordsSnapshot,
    ) -> None:
        await client.branch.merge(branch_name=schema_change_dataset.branch_name)

        card_schema = await client.schema.get(kind=CARD_KIND, branch="main", refresh=True)
        assert SERIAL_ATTRIBUTE in card_schema.attribute_names
        assert await take_records_snapshot(db=db, branch_name=schema_change_dataset.branch_name) == records_before
