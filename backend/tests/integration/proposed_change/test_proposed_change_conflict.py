from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.protocols import CoreDataCheck, CoreProposedChange

from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreProposedChange as InternalCoreProposedChange
from infrahub.core.protocols import CoreValidator
from infrahub.proposed_change.constants import ProposedChangeState
from infrahub.services.adapters.cache.redis import RedisCache
from infrahub.utils import get_fixtures_dir
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestProposedChangePipelineConflict(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def car_dealership_copy(self):
        """
        Copies car-dealership local repository to a temporary folder, with a new name.
        This is needed for this test as using car-dealership folder leads to issues most probably
        related to https://github.com/opsmill/infrahub/issues/4296 as some other tests use this same repository.
        """

        source_folder = Path(get_fixtures_dir(), "repos", "car-dealership")
        new_folder_name = "car-dealership-copy"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            destination_folder = temp_path / new_folder_name
            shutil.copytree(source_folder, destination_folder)
            yield temp_path, new_folder_name

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        car_dealership_copy: tuple[Path, str],
    ) -> str:
        await load_schema(db, schema=CAR_SCHEMA)
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

        bus_simulator.service.cache = RedisCache()
        repo_path, repo_name = car_dealership_copy
        FileRepo(name=repo_name, local_repo_base_path=repo_path, sources_directory=git_repos_source_dir_module_scope)
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "dealership-car", "location": f"{git_repos_source_dir_module_scope}/{repo_name}"},
        )
        await client_repository.save()
        return client_repository.id

    @pytest.fixture(scope="class")
    async def happy_dataset(self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> None:
        branch1 = await client.branch.create(branch_name="conflict_free")
        richard = await Node.init(schema=TestKind.PERSON, db=db, branch=branch1.name)
        await richard.new(db=db, name="Richard", height=180, description="The less famous Richard Doe")
        await richard.save(db=db)

        john = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id="John", kind=TestKind.PERSON, branch=branch1.name
        )
        john.age.value = 26  # type: ignore[attr-defined]
        await john.save(db=db)

    @pytest.fixture(scope="class")
    async def conflict_dataset(self, db: InfrahubDatabase, initial_dataset: None) -> None:
        branch1 = await create_branch(db=db, branch_name="conflict_data")
        john = await NodeManager.get_one_by_id_or_default_filter(db=db, id="John", kind=TestKind.PERSON)
        john.description.value = "Who is this?"  # type: ignore[attr-defined]
        await john.save(db=db)

        john_branch = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id="John", kind=TestKind.PERSON, branch=branch1
        )
        john_branch.description.value = "Oh boy"  # type: ignore[attr-defined]
        john_branch.age.value = 30  # type: ignore[attr-defined]
        await john_branch.save(db=db)

    async def test_conflict_pipeline(
        self, db: InfrahubDatabase, conflict_dataset: None, client: InfrahubClient
    ) -> None:
        proposed_change_create = await client.create(
            kind=CoreProposedChange,
            data={"source_branch": "conflict_data", "destination_branch": "main", "name": "conflict_test"},
        )
        await proposed_change_create.save()

        # -------------------------------------------------
        # Ensure that the data integrity validator is reporting a failure
        # -------------------------------------------------
        proposed_change = await NodeManager.get_one(
            db=db, id=proposed_change_create.id, kind=InternalCoreProposedChange, raise_on_error=True
        )
        peers = await proposed_change.validations.get_peers(db=db, peer_type=CoreValidator)
        assert peers
        data_integrity = [validator for validator in peers.values() if validator.label.value == "Data Integrity"][0]
        assert data_integrity.conclusion.value.value == ValidatorConclusion.FAILURE.value

        proposed_change_create.state.value = ProposedChangeState.MERGED.value

        data_checks = await client.filters(kind=CoreDataCheck, validator__ids=data_integrity.id)
        assert len(data_checks) == 1
        data_check = data_checks[0]

        # -------------------------------------------------
        # Try to merge and ensure the proposed change is back to open state
        # -------------------------------------------------
        with pytest.raises(
            GraphQLError, match="Data conflicts found on branch and missing decisions about what branch to keep"
        ):
            await proposed_change_create.save()

        proposed_change_after = await client.get(kind=CoreProposedChange, id=proposed_change_create.id)
        assert proposed_change_after.state.value == ProposedChangeState.OPEN.value

        # -------------------------------------------------
        # Fix the conflict and try to merge again
        # -------------------------------------------------
        query = """
        mutation ($id: String!) {
            ResolveDiffConflict(
                data: {
                    conflict_id: $id
                    selected_branch: DIFF_BRANCH
                }
            ){
                ok
            }
        }
        """
        await client.execute_graphql(query=query, variables={"id": data_check.enriched_conflict_id.value})

        proposed_change_after.state.value = ProposedChangeState.MERGED.value
        await proposed_change_after.save()
        john = await NodeManager.get_one_by_default_filter(db=db, id="John", kind=TestKind.PERSON)
        # The value of the description should match that of the source branch that was selected
        # as the branch to keep in the data conflict
        assert john.description.value == "Oh boy"  # type: ignore[attr-defined]

    async def test_happy_pipeline(self, db: InfrahubDatabase, happy_dataset: None, client: InfrahubClient) -> None:
        proposed_change_create = await client.create(
            kind=CoreProposedChange,
            data={"source_branch": "conflict_free", "destination_branch": "main", "name": "happy-test"},
        )
        await proposed_change_create.save()

        # -------------------------------------------------
        # Ensure that all validators have been executed and aren't reporting errors
        # -------------------------------------------------
        proposed_change = await NodeManager.get_one(
            db=db, id=proposed_change_create.id, kind=InternalCoreProposedChange, raise_on_error=True
        )
        peers = await proposed_change.validations.get_peers(db=db, peer_type=CoreValidator)
        assert peers

        data_integrity = [validator for validator in peers.values() if validator.label.value == "Data Integrity"][0]
        assert data_integrity.conclusion.value.value == ValidatorConclusion.SUCCESS.value
        ownership_artifacts = [
            validator for validator in peers.values() if validator.label.value == "Artifact Validator: Ownership report"
        ][0]
        assert ownership_artifacts.conclusion.value.value == ValidatorConclusion.SUCCESS.value
        description_check = [
            validator for validator in peers.values() if validator.label.value == "Check: car_description_check"
        ][0]
        assert description_check.conclusion.value.value == ValidatorConclusion.SUCCESS.value
        age_check = [validator for validator in peers.values() if validator.label.value == "Check: owner_age_check"][0]
        assert age_check.conclusion.value.value == ValidatorConclusion.SUCCESS.value

        repository_merge_conflict = [
            validator for validator in peers.values() if validator.label.value == "Repository Validator: dealership-car"
        ][0]
        assert repository_merge_conflict.conclusion.value.value == ValidatorConclusion.SUCCESS.value

        tags = await client.all(kind="BuiltinTag", branch="conflict_free")
        # The Generator defined in the repository is expected to have created this tag during the pipeline
        assert "john-jesko" in [tag.name.value for tag in tags]  # type: ignore[attr-defined]
        assert "InfrahubNode-john-jesko" in [tag.name.value for tag in tags]  # type: ignore[attr-defined]

        # -------------------------------------------------
        # Merge the proposed change and ensure everything looks good
        # -------------------------------------------------
        proposed_change_create.state.value = ProposedChangeState.MERGED.value
        await proposed_change_create.save()

        proposed_change_after = await client.get(kind=CoreProposedChange, id=proposed_change_create.id)
        assert proposed_change_after.state.value == ProposedChangeState.MERGED.value

    async def test_connectivity(self, db: InfrahubDatabase, initial_dataset: str, client: InfrahubClient) -> None:
        """Validate that the request to check connectivity to the remote repository is successful"""
        query = """
        mutation InfrahubRepositoryConnectivity($id: String!) {
            InfrahubRepositoryConnectivity(data: {id: $id}) {
                ok
                message
            }
        }
        """
        result = await client.execute_graphql(query=query, variables={"id": initial_dataset})
        assert result["InfrahubRepositoryConnectivity"]["ok"]
        assert result["InfrahubRepositoryConnectivity"]["message"] == "Successfully accessed repository"
