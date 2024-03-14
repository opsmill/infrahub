from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase


class TestProposedChangePipeline(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(self, db: InfrahubDatabase, initialize_registry: None) -> None:
        await load_schema(db, schema=CAR_SCHEMA)
        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)

    @pytest.fixture(scope="class")
    async def happy_dataset(self, db: InfrahubDatabase, initial_dataset: None) -> None:
        branch1 = await create_branch(db=db, branch_name="conflict_free")
        richard = await Node.init(schema=TestKind.PERSON, db=db, branch=branch1)
        await richard.new(db=db, name="Richard", height=180, description="The less famous Richard Doe")
        await richard.save(db=db)

    @pytest.fixture(scope="class")
    async def conflict_dataset(self, db: InfrahubDatabase, initial_dataset: None) -> None:
        branch1 = await create_branch(db=db, branch_name="conflict_data")
        john = await NodeManager.get_one_by_id_or_default_filter(db=db, id="John", schema_name=TestKind.PERSON)
        john.description.value = "Who is this?"  # type: ignore[attr-defined]
        await john.save(db=db)

        john_branch = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id="John", schema_name=TestKind.PERSON, branch=branch1
        )
        john_branch.description.value = "Oh boy"  # type: ignore[attr-defined]
        await john_branch.save(db=db)

    async def test_happy_pipeline(self, db: InfrahubDatabase, happy_dataset: None, client: InfrahubClient) -> None:
        proposed_change_create = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={"source_branch": "conflict_free", "destination_branch": "main", "name": "happy-test"},
        )
        await proposed_change_create.save()

        proposed_change = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id=proposed_change_create.id, schema_name=InfrahubKind.PROPOSEDCHANGE
        )
        peers = await proposed_change.validations.get_peers(db=db)  # type: ignore[attr-defined]
        assert peers
        data_integrity = [validator for validator in peers.values() if validator.label.value == "Data Integrity"][0]
        assert data_integrity.conclusion.value == ValidatorConclusion.SUCCESS.value

    async def test_conflict_pipeline(
        self, db: InfrahubDatabase, conflict_dataset: None, client: InfrahubClient
    ) -> None:
        proposed_change_create = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={"source_branch": "conflict_data", "destination_branch": "main", "name": "conflict_test"},
        )
        await proposed_change_create.save()

        proposed_change = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id=proposed_change_create.id, schema_name=InfrahubKind.PROPOSEDCHANGE
        )
        peers = await proposed_change.validations.get_peers(db=db)  # type: ignore[attr-defined]
        assert peers
        data_integrity = [validator for validator in peers.values() if validator.label.value == "Data Integrity"][0]
        assert data_integrity.conclusion.value == ValidatorConclusion.FAILURE.value
