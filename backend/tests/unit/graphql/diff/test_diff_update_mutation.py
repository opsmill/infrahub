import pytest

from infrahub.core.branch import Branch
from infrahub.core.diff.model.path import EnrichedDiffRootMetadata, NameTrackingId
from infrahub.core.diff.parent_node_adder import DiffParentNodeAdder
from infrahub.core.diff.repository.deserializer import EnrichedDiffDeserializer
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder
from tests.helpers.graphql import graphql

DIFF_UPDATE_MUTATION = """
    mutation($branch: String!, $name: String, $from_time: DateTime, $to_time: DateTime, $wait_until_completion: Boolean = true) {
        DiffUpdate(
            data: {
                branch: $branch,
                name: $name,
                from_time: $from_time,
                to_time: $to_time
            },
            wait_until_completion: $wait_until_completion
        ) {
            ok
            task {
                id
            }
        }
    }
"""


class TestDiffUpdateMutation:
    diff_name = "CountDiffula"

    @pytest.fixture
    async def service_testing(self, db: InfrahubDatabase) -> InfrahubServices:
        return await InfrahubServices.new(
            database=db, message_bus=BusRecorder(), workflow=WorkflowLocalExecution(), cache=MemoryCache()
        )

    @pytest.fixture
    async def diff_branch(self, db: InfrahubDatabase) -> Branch:
        return await create_branch(db=db, branch_name="branch")

    @pytest.fixture
    async def named_diff(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        prefect_test_fixture,
        service_testing: InfrahubServices,
        criticality_schema,
        diff_branch: Branch,
    ) -> EnrichedDiffRootMetadata:
        default_branch.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch, service=service_testing)
        result = await graphql(
            schema=params.schema,
            source=DIFF_UPDATE_MUTATION,
            context_value=params.context,
            root_value=None,
            variable_values={"branch": diff_branch.name, "name": self.diff_name},
        )
        assert result.errors is None
        assert result.data
        assert result.data["DiffUpdate"]["ok"] is True

        diff_repo = DiffRepository(db=db, deserializer=EnrichedDiffDeserializer(DiffParentNodeAdder()))
        return (
            await diff_repo.get_roots_metadata(
                diff_branch_names=[diff_branch.name],
                base_branch_names=[default_branch.name],
                tracking_id=NameTrackingId(name=self.diff_name),
            )
        )[0]

    async def test_create_diff_before_branched_from_fails(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        prefect_test_fixture,
        service_testing: InfrahubServices,
        criticality_schema,
        diff_branch: Branch,
    ):
        branched_from_timestamp = Timestamp(diff_branch.get_branched_from())
        default_branch.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch, service=service_testing)
        result = await graphql(
            schema=params.schema,
            source=DIFF_UPDATE_MUTATION,
            context_value=params.context,
            root_value=None,
            variable_values={
                "branch": diff_branch.name,
                "name": self.diff_name,
                "from_time": branched_from_timestamp.add(seconds=-1).to_string(),
            },
        )
        assert result.errors is None
        assert result.data
        assert result.data["DiffUpdate"]["ok"] is True

    async def test_create_time_range_diff_without_name_fails(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        prefect_test_fixture,
        service_testing: InfrahubServices,
        criticality_schema,
        diff_branch: Branch,
    ):
        branched_from_timestamp = Timestamp(diff_branch.get_branched_from())
        default_branch.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch, service=service_testing)
        result = await graphql(
            schema=params.schema,
            source=DIFF_UPDATE_MUTATION,
            context_value=params.context,
            root_value=None,
            variable_values={
                "branch": diff_branch.name,
                "from_time": branched_from_timestamp.to_string(),
                "to_time": Timestamp().to_string(),
            },
        )
        assert result.errors is not None
        assert len(result.errors) == 1
        assert "diff with specified time range requires a name" in result.errors[0].message

    async def test_create_diff_with_illegal_times_fails(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        prefect_test_fixture,
        service_testing: InfrahubServices,
        criticality_schema,
        diff_branch: Branch,
        named_diff: EnrichedDiffRootMetadata,
    ):
        default_branch.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch, service=service_testing)
        result = await graphql(
            schema=params.schema,
            source=DIFF_UPDATE_MUTATION,
            context_value=params.context,
            root_value=None,
            variable_values={
                "branch": diff_branch.name,
                "name": self.diff_name,
                "from_time": named_diff.from_time.add(microseconds=-1).to_string(),
            },
        )
        assert result.errors is not None
        assert len(result.errors) == 1
        assert "from_time must be null or greater than or equal to " in result.errors[0].message

        result = await graphql(
            schema=params.schema,
            source=DIFF_UPDATE_MUTATION,
            context_value=params.context,
            root_value=None,
            variable_values={
                "branch": diff_branch.name,
                "name": self.diff_name,
                "to_time": named_diff.to_time.add(seconds=-1).to_string(),
            },
        )
        assert result.errors is not None
        assert len(result.errors) == 1
        assert "to_time must be null or greater than or equal to " in result.errors[0].message

    async def test_create_named_diff_with_legal_times_succeeds(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        prefect_test_fixture,
        service_testing: InfrahubServices,
        criticality_schema,
        diff_branch: Branch,
        named_diff: EnrichedDiffRootMetadata,
    ):
        branched_from_timestamp = Timestamp(diff_branch.get_branched_from())
        default_branch.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch, service=service_testing)
        result = await graphql(
            schema=params.schema,
            source=DIFF_UPDATE_MUTATION,
            context_value=params.context,
            root_value=None,
            variable_values={
                "branch": diff_branch.name,
                "from_time": branched_from_timestamp.to_string(),
                "to_time": Timestamp().to_string(),
                "name": self.diff_name,
            },
        )
        assert result.errors is None
        assert result.data["DiffUpdate"]["ok"] is True

    async def test_retrieve_task_id(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        prefect_test_fixture,
        service_testing: InfrahubServices,
        criticality_schema,
        diff_branch: Branch,
        named_diff: EnrichedDiffRootMetadata,
    ):
        branched_from_timestamp = Timestamp(diff_branch.get_branched_from())
        default_branch.update_schema_hash()
        params = await prepare_graphql_params(db=db, branch=default_branch, service=service_testing)
        result = await graphql(
            schema=params.schema,
            source=DIFF_UPDATE_MUTATION,
            context_value=params.context,
            root_value=None,
            variable_values={
                "branch": diff_branch.name,
                "from_time": branched_from_timestamp.to_string(),
                "to_time": Timestamp().to_string(),
                "name": self.diff_name,
                "wait_until_completion": False,
            },
        )
        assert result.errors is None
        assert result.data["DiffUpdate"]["ok"] is True
        assert result.data["DiffUpdate"]["task"]["id"] is not None
