from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.services.adapters.cache.redis import RedisCache
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestProposedChangePipelineConflict(TestInfrahubApp):
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

        bus_simulator.service.cache = RedisCache()

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
        await jesko.new(
            db=db,
            name="Jesko",
            color="Red",
            description="A limited production mid-engine sports car",
            owner=john,
            manufacturer=koenigsegg,
        )
        await jesko.save(db=db)

        branch1 = await client.branch.create(branch_name="branch1")

        FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
            branch=branch1.name,
        )
        await client_repository.save()

        richard = await Node.init(schema=TestKind.PERSON, db=db, branch=branch1.name)
        await richard.new(db=db, name="Richard", height=180, description="The less famous Richard Doe")
        await richard.save(db=db)

    async def test_create_proposed_change(
        self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient
    ) -> None:
        proposed_change_create = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={"source_branch": "branch1", "destination_branch": "main", "name": "add repository"},
        )
        await proposed_change_create.save()

        proposed_change = await NodeManager.get_one(
            db=db, id=proposed_change_create.id, kind=InfrahubKind.PROPOSEDCHANGE, raise_on_error=True
        )
        peers = await proposed_change.validations.get_peers(db=db)  # type: ignore[attr-defined]
        assert peers
        data_integrity = [validator for validator in peers.values() if validator.label.value == "Data Integrity"][0]
        assert data_integrity.conclusion.value.value == ValidatorConclusion.SUCCESS.value

        # ownership_artifacts = [
        #     validator for validator in peers.values() if validator.label.value == "Artifact Validator: Ownership report"
        # ][0]
        # assert ownership_artifacts.conclusion.value.value == ValidatorConclusion.SUCCESS.value
        # description_check = [
        #     validator for validator in peers.values() if validator.label.value == "Check: car_description_check"
        # ][0]
        # assert description_check.conclusion.value.value == ValidatorConclusion.SUCCESS.value
        # age_check = [validator for validator in peers.values() if validator.label.value == "Check: owner_age_check"][0]
        # assert age_check.conclusion.value.value == ValidatorConclusion.SUCCESS.value

        # repository_merge_conflict = [
        #     validator for validator in peers.values() if validator.label.value == "Repository Validator: car-dealership"
        # ][0]
        # assert repository_merge_conflict.conclusion.value.value == ValidatorConclusion.SUCCESS.value

        # tags = await client.all(kind="BuiltinTag", branch="branch1")
        # # The Generator defined in the repository is expected to have created this tag during the pipeline
        # assert "john-jesko" in [tag.name.value for tag in tags]  # type: ignore[attr-defined]
        # assert "InfrahubNode-john-jesko" in [tag.name.value for tag in tags]  # type: ignore[attr-defined]

        # proposed_change_create.state.value = "merged"  # type: ignore[attr-defined]
        # await proposed_change_create.save()
