"""A cross-branch change to the same cardinality-one relationship is a resolvable data conflict.

The schema-integrity check must not additionally report it as a (non-resolvable) relationship-count
violation, which would hard-block a proposed change that is otherwise resolvable.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.protocols import CoreProposedChange as SdkCoreProposedChange

from infrahub.core.constants import ValidatorConclusion
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreProposedChange
from tests.constants import TestKind
from tests.helpers.constants import PREFECT_EVENT_WAIT_SECONDS
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

SCHEMA_INTEGRITY_LABEL = "Schema Integrity"
DATA_INTEGRITY_LABEL = "Data Integrity"


class TestProposedChangeCardinalityOneConflict(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> dict[str, str]:
        await load_schema(db, schema=CAR_SCHEMA)

        koenigsegg = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await koenigsegg.new(db=db, name="Koenigsegg")
        await koenigsegg.save(db=db)
        cyberdyne = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await cyberdyne.new(db=db, name="Cyberdyne")
        await cyberdyne.save(db=db)
        omnicorp = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await omnicorp.new(db=db, name="Omnicorp")
        await omnicorp.save(db=db)
        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175)
        await john.save(db=db)
        jesko = await Node.init(schema=TestKind.CAR, db=db)
        await jesko.new(db=db, name="Jesko", color="Red", owner=john, manufacturer=koenigsegg)
        await jesko.save(db=db)

        return {"car_id": jesko.id, "cyberdyne_id": cyberdyne.id, "omnicorp_id": omnicorp.id}

    async def test_cardinality_one_conflict_is_not_a_schema_violation(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        initial_dataset: dict[str, str],
        client: InfrahubClient,
    ) -> None:
        branch = await client.branch.create(branch_name="rival_manufacturers")
        car_on_branch = await NodeManager.get_one(db=db, id=initial_dataset["car_id"], branch=branch.name)
        assert car_on_branch
        await car_on_branch.get_relationship("manufacturer").update(db=db, data={"id": initial_dataset["omnicorp_id"]})
        await car_on_branch.save(db=db)

        car_on_main = await NodeManager.get_one(db=db, id=initial_dataset["car_id"], branch=default_branch)
        assert car_on_main
        await car_on_main.get_relationship("manufacturer").update(db=db, data={"id": initial_dataset["cyberdyne_id"]})
        await car_on_main.save(db=db)

        proposed_change_create = await client.create(
            kind=SdkCoreProposedChange,
            data={"source_branch": branch.name, "destination_branch": "main", "name": "rival-manufacturers"},
        )
        await proposed_change_create.save()

        schema_validator = None
        data_validator = None
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            proposed_change = await NodeManager.get_one(db=db, id=proposed_change_create.id, kind=CoreProposedChange)
            assert proposed_change
            peers = await proposed_change.validations.get_peers(db=db)
            labels = {v.label.value: v for v in peers.values()}
            if SCHEMA_INTEGRITY_LABEL in labels and DATA_INTEGRITY_LABEL in labels:
                schema_validator = labels[SCHEMA_INTEGRITY_LABEL]
                data_validator = labels[DATA_INTEGRITY_LABEL]
                break
            await asyncio.sleep(1)

        assert data_validator is not None, "Data Integrity validator was not produced"
        assert schema_validator is not None, "Schema Integrity validator was not produced"
        # Sanity check: this really is a (resolvable) data conflict.
        assert data_validator.conclusion.value.value == ValidatorConclusion.FAILURE.value
        # The cardinality-one peer change is handled as a resolvable data conflict; it must not be
        # flagged as a non-resolvable relationship-count violation here.
        assert schema_validator.conclusion.value.value == ValidatorConclusion.SUCCESS.value
