import base64
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

import cloudpickle
from prefect.deployments import run_deployment

from infrahub.workflows.models import WorkflowDefinition

from . import InfrahubWorkflow, Return

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun


class WorkflowWorkerExecution(InfrahubWorkflow):
    async def execute(
        self,
        workflow: WorkflowDefinition | None = None,
        function: Callable[..., Awaitable[Return]] | None = None,
        **kwargs: Any,
    ) -> Return:
        if workflow:
            response: FlowRun = await run_deployment(name=workflow.full_name, parameters=kwargs or {})  # type: ignore[return-value, misc]
            if not response.state:
                raise RuntimeError("Unable to read state from the response")
            result = response.state.result()

            with Path(result.storage_key).open(encoding="utf-8") as f:
                result_data = json.load(f)
            encoded_data = result_data["data"]
            decoded_data = base64.b64decode(encoded_data)

            if result_data["serializer"]["type"] == "pickle":
                return cloudpickle.loads(decoded_data)
            raise ValueError("Unsupported serializer type")

        if function:
            return await function(**kwargs)

        raise ValueError("either a workflow definition or a flow must be provided")
