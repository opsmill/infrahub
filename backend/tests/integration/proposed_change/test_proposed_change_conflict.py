from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import uuid4

import pytest
from infrahub_sdk.context import ContextAccount, RequestContext
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.protocols import CoreDataCheck, CoreProposedChange

from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.initialization import create_account, create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.merge import BranchMerger
from infrahub.core.node import Node
from infrahub.core.protocols import CoreProposedChange as InternalCoreProposedChange
from infrahub.core.protocols import CoreValidator
from infrahub.proposed_change.constants import ProposedChangeState
from infrahub.utils import get_fixtures_dir
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.diff.model.path import EnrichedDiffRoot
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class ErroringBranchMerger(BranchMerger):
    async def merge(
        self,
        at: str | Timestamp | None = None,
    ) -> EnrichedDiffRoot:
        raise ValueError("This will always fail")


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

        repo_path, repo_name = car_dealership_copy
        FileRepo(name=repo_name, local_repo_base_path=repo_path, sources_directory=git_repos_source_dir_module_scope)
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "dealership-car", "location": f"{git_repos_source_dir_module_scope}/{repo_name}"},
        )
        await client_repository.save()
        return client_repository.id

    @pytest.fixture(scope="class")
    async def happy_data_branch(self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> str:
        branch_name = f"conflict_free-{uuid4()}"
        branch1 = await client.branch.create(branch_name=branch_name)
        richard = await Node.init(schema=TestKind.PERSON, db=db, branch=branch1.name)
        await richard.new(db=db, name="Richard", height=180, description="The less famous Richard Doe")
        await richard.save(db=db)

        john = await NodeManager.get_one_by_id_or_default_filter(
            db=db, id="John", kind=TestKind.PERSON, branch=branch1.name
        )
        john.name.value = "Johnny"  # type: ignore[attr-defined]
        john.age.value = 26  # type: ignore[attr-defined]
        await john.save(db=db)
        return branch_name

    @pytest.fixture(scope="class")
    async def failing_branch_dataset(self, db: InfrahubDatabase, initial_dataset: None, client: InfrahubClient) -> None:
        branch1 = await client.branch.create(branch_name="failing_branch")
        steve = await Node.init(schema=TestKind.PERSON, db=db, branch=branch1.name)
        await steve.new(db=db, name="Steve", height=178)
        await steve.save(db=db)

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
        assert john.description.value == "Oh boy"  # type: ignore[attr-defined, union-attr]

    async def test_happy_pipeline(self, db: InfrahubDatabase, happy_data_branch: str, client: InfrahubClient) -> None:
        proposed_change_user = await create_account(db=db, name="jimmy-change-user", password="Password123")
        # The state=open part here is to validate that the state check during creation of a
        # proposed change still works if the default "open" state is manually specified
        proposed_change_create = await client.create(
            kind=CoreProposedChange,
            data={
                "source_branch": happy_data_branch,
                "destination_branch": "main",
                "name": "happy-test",
                "state": "open",
            },
        )
        await proposed_change_create.save(
            request_context=RequestContext(account=ContextAccount(id=proposed_change_user.id))
        )

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
        converted_owner_artifacts = [
            validator for validator in peers.values() if validator.label.value == "Artifact Validator: converted-owner"
        ][0]
        assert converted_owner_artifacts.conclusion.value.value == ValidatorConclusion.SUCCESS.value
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

        tags = await client.all(kind="BuiltinTag", branch=happy_data_branch)
        # The Generator defined in the repository is expected to have created this tag during the pipeline
        assert "johnny-jesko" in [tag.name.value for tag in tags]  # type: ignore[attr-defined]
        assert "InfrahubNode-johnny-jesko" in [tag.name.value for tag in tags]  # type: ignore[attr-defined]

        # -------------------------------------------------
        # Merge the proposed change and ensure everything looks good
        # -------------------------------------------------
        proposed_change_create.state.value = ProposedChangeState.MERGED.value
        await proposed_change_create.save()

        proposed_change_after = await client.get(kind=CoreProposedChange, id=proposed_change_create.id)
        assert proposed_change_after.state.value == ProposedChangeState.MERGED.value

        for _ in range(10):
            merge_event = await client.execute_graphql(
                query=QUERY_EVENT,
                variables={
                    "event_type_filter": {"branch_merged": {"branches": happy_data_branch}},
                },
            )
            if merge_event["InfrahubEvent"]["count"] == 1:
                break
            await asyncio.sleep(1)

        assert merge_event["InfrahubEvent"]["count"] == 1
        merge_event_id = merge_event["InfrahubEvent"]["edges"][0]["node"]["id"]
        assert len(merge_event["InfrahubEvent"]["edges"][0]["node"]["related_nodes"]) == 1
        assert merge_event["InfrahubEvent"]["edges"][0]["node"]["related_nodes"][0]["id"] == proposed_change.id

        john = await NodeManager.get_one_by_id_or_default_filter(db=db, id="Johnny", kind=TestKind.PERSON)
        richard = await NodeManager.get_one_by_id_or_default_filter(db=db, id="Richard", kind=TestKind.PERSON)

        # Use this sleep mechanism to wait for the events being fired
        for _ in range(10):
            secondary_events = await client.execute_graphql(
                query=QUERY_EVENT, variables={"parent__ids": merge_event_id}
            )
            if secondary_events["InfrahubEvent"]["count"] >= 3:
                break
            await asyncio.sleep(1)

        assert secondary_events["InfrahubEvent"]["count"] >= 3

        johns_events = [
            event
            for event in secondary_events["InfrahubEvent"]["edges"]
            if event["node"]["primary_node"]["id"] == john.id
        ]
        richards_events = [
            event
            for event in secondary_events["InfrahubEvent"]["edges"]
            if event["node"]["primary_node"]["id"] == richard.id
        ]
        assert len(johns_events) == 1
        assert len(richards_events) == 1

        assert johns_events[0]["node"]["event"] == "infrahub.node.updated"
        assert richards_events[0]["node"]["event"] == "infrahub.node.created"

        artifact_events = await client.execute_graphql(
            query=QUERY_EVENT,
            variables={"branch": [happy_data_branch], "event_type": ["infrahub.artifact.updated"]},
        )
        assert artifact_events["InfrahubEvent"]["count"] > 0
        latest_artifact_event = artifact_events["InfrahubEvent"]["edges"][0]["node"]
        assert sorted(latest_artifact_event.keys()) == [
            "account_id",
            "artifact_definition_id",
            "branch",
            "checksum",
            "checksum_previous",
            "event",
            "has_children",
            "id",
            "level",
            "occurred_at",
            "parent_id",
            "primary_node",
            "related_nodes",
            "storage_id",
            "storage_id_previous",
        ]
        assert len(latest_artifact_event["related_nodes"]) == 1
        assert latest_artifact_event["related_nodes"][0]["kind"] == "TestingPerson"
        validator_started_events = await client.execute_graphql(
            query=QUERY_EVENT,
            variables={"related_node__ids": [proposed_change_after.id], "event_type": ["infrahub.validator.started"]},
        )
        validator_passed_events = await client.execute_graphql(
            query=QUERY_EVENT,
            variables={"related_node__ids": [proposed_change_after.id], "event_type": ["infrahub.validator.passed"]},
        )
        assert validator_started_events["InfrahubEvent"]["count"] == 11
        assert validator_passed_events["InfrahubEvent"]["count"] == 11
        started_validators = [
            event["node"]["primary_node"]["kind"] for event in validator_started_events["InfrahubEvent"]["edges"]
        ]
        passed_validators = [
            event["node"]["primary_node"]["kind"] for event in validator_passed_events["InfrahubEvent"]["edges"]
        ]
        assert sorted(started_validators) == [
            "CoreArtifactValidator",
            "CoreArtifactValidator",
            "CoreArtifactValidator",
            "CoreArtifactValidator",
            "CoreArtifactValidator",
            "CoreGeneratorValidator",
            "CoreGeneratorValidator",
            "CoreRepositoryValidator",
            "CoreUserValidator",
            "CoreUserValidator",
        ]
        assert sorted(passed_validators) == [
            "CoreArtifactValidator",
            "CoreArtifactValidator",
            "CoreArtifactValidator",
            "CoreArtifactValidator",
            "CoreArtifactValidator",
            "CoreGeneratorValidator",
            "CoreGeneratorValidator",
            "CoreRepositoryValidator",
            "CoreUserValidator",
            "CoreUserValidator",
        ]

        pr_account_events = await client.execute_graphql(
            query=QUERY_EVENT,
            variables={"account__ids": [proposed_change_user.id]},
        )
        pr_account_events_types = {event["node"]["event"] for event in pr_account_events["InfrahubEvent"]["edges"]}
        assert "infrahub.validator.passed" in pr_account_events_types
        assert "infrahub.artifact.updated" in pr_account_events_types

    async def test_merge_failure(
        self,
        db: InfrahubDatabase,
        failing_branch_dataset: None,
        client: InfrahubClient,
    ) -> None:
        proposed_change_create = await client.create(
            kind=CoreProposedChange,
            data={"source_branch": "failing_branch", "destination_branch": "main", "name": "failing_branch-pr"},
        )
        await proposed_change_create.save()

        # -------------------------------------------------
        # Merge the proposed change and ensure everything looks good
        # -------------------------------------------------
        proposed_change_create.state.value = ProposedChangeState.MERGED.value
        with patch("infrahub.core.branch.tasks.BranchMerger", new=ErroringBranchMerger):
            with pytest.raises(GraphQLError) as exc:
                await proposed_change_create.save()
                assert "Failed to merge branch 'failing_branch'" in exc.value.message

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


QUERY_EVENT = """
query(
    $branch: [String!],
    $parent__ids: [String!],
    $event_type: [String!]
    $account__ids: [String!],
    $related_node__ids: [String!],
    $event_type_filter: EventTypeFilter
) {
  InfrahubEvent(
    branches: $branch,
    parent__ids: $parent__ids
    event_type: $event_type
    event_type_filter: $event_type_filter
    account__ids: $account__ids
    related_node__ids: $related_node__ids
  ) {
    count
    edges {
      node {
        id
        event
        branch
        has_children
        parent_id
        level
        occurred_at
        account_id
        primary_node {
          id
          kind
        }
        related_nodes {
            id
            kind
        }
        ... on ArtifactEvent {
          id
          artifact_definition_id
          storage_id
          storage_id_previous
          checksum_previous
          checksum
        }
       ... on NodeMutatedEvent {
          id
          attributes {
            name
            value
            value_previous
          }
        }
      }
    }
  }
}
"""
