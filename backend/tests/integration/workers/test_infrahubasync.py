from typing import TYPE_CHECKING

import pytest
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import StateType
from prefect.deployments import run_deployment
from pydantic import ValidationError

from infrahub import __version__ as infrahub_version
from infrahub.core.branch import Branch
from infrahub.database import InfrahubDatabase
from infrahub.tasks.dummy import DUMMY_FLOW, DUMMY_FLOW_BROKEN, DummyInput, DummyOutput
from infrahub.workers.infrahub_async import (
    WORKER_DEFAULT_RESULT_STORAGE_BLOCK,
    WORKER_QUERY_SECONDS,
    InfrahubWorkerAsync,
)
from tests.helpers.test_worker import TestWorkerInfrahubAsync

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun


class TestWorker(TestWorkerInfrahubAsync):
    async def test_flow_configuration(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
        dummy_flows_deployment,
        client,
    ):
        # Schedule the execution of the deployment from the server
        flow: FlowRun = await run_deployment(
            name=DUMMY_FLOW.full_name, parameters={"data": DummyInput(firstname="John", lastname="Doe")}, timeout=0
        )  # type: ignore[return-value, misc]

        # Prepare the execution of the flow, pull the information about the deployment
        assert flow.deployment_id
        deployment = await prefect_client.read_deployment(deployment_id=flow.deployment_id)
        flow_config = await prefect_worker._get_configuration(flow_run=flow, deployment=deployment)

        assert "PREFECT_WORKER_QUERY_SECONDS" in flow_config.env
        assert flow_config.env.get("PREFECT_WORKER_QUERY_SECONDS") == WORKER_QUERY_SECONDS

        assert "PREFECT_DEFAULT_RESULT_STORAGE_BLOCK" in flow_config.env
        assert flow_config.env.get("PREFECT_DEFAULT_RESULT_STORAGE_BLOCK") == WORKER_DEFAULT_RESULT_STORAGE_BLOCK

        assert "infrahub.app/version" in flow_config.labels
        assert flow_config.labels.get("infrahub.app/version") == infrahub_version

        # delete the flow
        await prefect_client.delete_flow_run(flow_run_id=flow.id)

    async def test_successfull_flow(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
        dummy_flows_deployment,
        client,
    ):
        # Schedule the execution of the deployment from the server
        flow: FlowRun = await run_deployment(
            name=DUMMY_FLOW.full_name, parameters={"data": DummyInput(firstname="John", lastname="Doe")}, timeout=0
        )  # type: ignore[return-value, misc]

        result_worker = await self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=flow)
        assert result_worker.status_code == 0

        # Check the status of the flow in Prefect after the run
        flow_after = await prefect_client.read_flow_run(flow_run_id=flow.id)
        assert flow_after.state
        assert flow_after.state.type == StateType.COMPLETED

        result = await flow_after.state.result(raise_on_failure=True, fetch=True)  # type: ignore[call-overload]
        assert isinstance(result, DummyOutput)
        assert result.full_name == "John, Doe"

    async def test_broken_flow(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        prefect_client: PrefectClient,
        prefect_worker: InfrahubWorkerAsync,
        dummy_flows_deployment,
        client,
    ):
        # Schedule the execution of the deployment from the server
        flow: FlowRun = await run_deployment(
            name=DUMMY_FLOW_BROKEN.full_name,
            parameters={"data": DummyInput(firstname="John", lastname="Doe")},
            timeout=0,
        )  # type: ignore[return-value, misc]

        result_worker = await self.worker_run_flow(worker=prefect_worker, client=prefect_client, flow=flow)
        assert result_worker.status_code == 0

        # Check the status of the flow in Prefect after the run
        flow_after = await prefect_client.read_flow_run(flow_run_id=flow.id)
        assert flow_after.state
        assert flow_after.state.type == StateType.FAILED

        with pytest.raises(ValidationError) as exc:
            await flow_after.state.result(raise_on_failure=True, fetch=True)  # type: ignore[call-overload]

        assert "validation error for DummyOutput" in str(exc.value)
