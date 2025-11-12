import asyncio
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator

import pytest
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import StateType
from prefect.deployments import run_deployment
from pydantic import ValidationError

from infrahub import __version__ as infrahub_version
from infrahub import config
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
    ) -> None:
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
    ) -> None:
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

        result = await flow_after.state.result(raise_on_failure=True)
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
    ) -> None:
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
            await flow_after.state.result(raise_on_failure=True)

        assert "validation error for DummyOutput" in str(exc.value)

    async def _run_git_command(self, *args: str) -> str | None:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip() if proc.returncode == 0 else None

    @pytest.fixture
    async def git_global_user_config(self) -> AsyncGenerator[None, None]:
        async def set_git_config(key: str, value: str | None) -> None:
            if value is not None:
                proc = await asyncio.create_subprocess_exec("git", "config", "--global", key, value)
            else:
                proc = await asyncio.create_subprocess_exec("git", "config", "--global", "--unset", key)
            await proc.wait()

        with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
            tmp_git_config = tmpfile.name

        previous_git_config_global = os.getenv("GIT_CONFIG_GLOBAL")
        os.environ["GIT_CONFIG_GLOBAL"] = tmp_git_config
        assert os.getenv("GIT_CONFIG_GLOBAL") and os.getenv("GIT_CONFIG_GLOBAL") == tmp_git_config

        initial_user_name = config.SETTINGS.git.user_name
        initial_user_email = config.SETTINGS.git.user_email

        user_name = "Test User"
        user_email = "test@email.com"

        await set_git_config("user.name", user_name)
        await set_git_config("user.email", user_email)
        config.SETTINGS.git.user_name = user_name
        config.SETTINGS.git.user_email = user_email

        yield

        config.SETTINGS.git.user_name = initial_user_name
        config.SETTINGS.git.user_email = initial_user_email

        if previous_git_config_global:
            os.environ["GIT_CONFIG_GLOBAL"] = previous_git_config_global
            assert os.getenv("GIT_CONFIG_GLOBAL") and os.getenv("GIT_CONFIG_GLOBAL") == previous_git_config_global
        else:
            os.environ.pop("GIT_CONFIG_GLOBAL", None)
            assert os.getenv("GIT_CONFIG_GLOBAL") is None

        try:
            Path(tmp_git_config).unlink()
        except FileNotFoundError:
            pass

    async def test_worker_has_set_git_user_config(self, client, work_pool, git_global_user_config) -> None:
        assert os.getenv("GIT_CONFIG_GLOBAL") is not None
        worker = InfrahubWorkerAsync(work_pool_name=work_pool.name)
        await worker.setup(client=client, metric_port=0)
        user_name = await self._run_git_command("config", "--global", "--get", "user.name")
        assert user_name == "Test User"

        user_email = await self._run_git_command("config", "--global", "--get", "user.email")
        assert user_email == "test@email.com"
