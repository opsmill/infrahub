from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind, TaskConclusion, ValidatorConclusion
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.task import Task
from infrahub.services.adapters.cache.redis import RedisCache
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestProposedChangePipelineProfile(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)

        car_profile = await Node.init(schema=f"Profile{TestKind.CAR}", db=db)
        await car_profile.new(db=db, profile_name="missing_description", description="missing description")
        await car_profile.save(db=db)

        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)
        koenigsegg = await Node.init(schema=TestKind.MANUFACTURER, db=db)
        await koenigsegg.new(db=db, name="Koenigsegg")
        await koenigsegg.save(db=db)
        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people", members=[john])
        await people.save(db=db)

        jesko = await Node.init(schema=TestKind.CAR, db=db)
        await jesko.new(db=db, name="Jesko", color="Red", owner=john, manufacturer=koenigsegg, profiles=[car_profile])
        await jesko.save(db=db)

        bus_simulator.service.cache = RedisCache()

    @pytest.fixture(scope="class")
    async def update_profile(self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> None:
        branch1 = await client.branch.create(branch_name="update_profile")
        profile1 = await NodeManager.get_one_by_default_filter(
            db=db, id="missing_description", kind=f"Profile{TestKind.CAR}", branch=branch1.name
        )
        assert profile1
        profile1.description.value = "MISSING DESCRIPTION"  # type: ignore[attr-defined]
        await profile1.save(db=db)

    async def test_pipeline(self, db: InfrahubDatabase, update_profile: None, client: InfrahubClient) -> None:
        proposed_change_create = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={"source_branch": "update_profile", "destination_branch": "main", "name": "PC1"},
        )
        await proposed_change_create.save()

        proposed_change = await NodeManager.get_one(
            db=db, id=proposed_change_create.id, kind=InfrahubKind.PROPOSEDCHANGE
        )
        assert proposed_change
        peers = await proposed_change.validations.get_peers(db=db)  # type: ignore[attr-defined]
        assert peers

        # Ensure all validators and all tasks are successfull
        assert all(
            validator.conclusion.value.value == ValidatorConclusion.SUCCESS.value for validator in peers.values()
        )

        tasks = await Task.query(db=db, ids=[], fields={}, related_nodes=[proposed_change.id], limit=10, offset=0)
        assert all(task["node"]["conclusion"] == TaskConclusion.SUCCESS for task in tasks["edges"])

        proposed_change_create.state.value = "merged"  # type: ignore[attr-defined]
        await proposed_change_create.save()
