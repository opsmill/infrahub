from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any, Dict, Optional

from httpx import HTTPStatusError

from infrahub_sdk.transforms import get_transform_class_instance

from ..exceptions import OutputMatchError, PythonTransformDefinitionError
from ..models import InfrahubTestExpectedResult
from .base import InfrahubItem

if TYPE_CHECKING:
    from pytest import ExceptionInfo

    from infrahub_sdk.pytest_plugin.models import InfrahubTest
    from infrahub_sdk.schema import InfrahubRepositoryConfigElement


class InfrahubPythonTransformItem(InfrahubItem):
    def __init__(
        self,
        *args: Any,
        resource_name: str,
        resource_config: InfrahubRepositoryConfigElement,
        test: InfrahubTest,
        **kwargs: Dict[str, Any],
    ):
        super().__init__(*args, resource_name=resource_name, resource_config=resource_config, test=test, **kwargs)

        self.transform_instance = get_transform_class_instance(
            transform_config=self.resource_config,  # type: ignore[arg-type]
            search_path=self.session.infrahub_config_path.parent,  # type: ignore[attr-defined]
        )

    def run_transform(self, variables: Dict[str, Any]) -> Any:
        return asyncio.run(self.transform_instance.run(data=variables))

    def repr_failure(self, excinfo: ExceptionInfo, style: Optional[str] = None) -> str:
        if isinstance(excinfo.value, HTTPStatusError):
            try:
                response_content = json.dumps(excinfo.value.response.json(), indent=4)
            except json.JSONDecodeError:
                response_content = excinfo.value.response.text
            return "\n".join(
                [
                    f"Failed {excinfo.value.request.method} on {excinfo.value.request.url}",
                    f"Status code: {excinfo.value.response.status_code}",
                    f"Response: {response_content}",
                ]
            )

        if isinstance(excinfo.value, OutputMatchError):
            return "\n".join([excinfo.value.message, excinfo.value.differences])

        return super().repr_failure(excinfo, style=style)


class InfrahubPythonTransformSmokeItem(InfrahubPythonTransformItem):
    def runtest(self) -> None:
        for attr in ("query", "transform"):
            if not hasattr(self.transform_instance, attr):
                raise PythonTransformDefinitionError(f"Missing attribute or function {attr}")


class InfrahubPythonTransformUnitProcessItem(InfrahubPythonTransformItem):
    def runtest(self) -> None:
        input_data = self.test.spec.get_input_data()  # type: ignore[union-attr]
        computed = self.run_transform(input_data)
        differences = self.get_result_differences(computed)

        if computed is not None and differences and self.test.expect == InfrahubTestExpectedResult.PASS:
            raise OutputMatchError(name=self.name, message=differences)


class InfrahubPythonTransformIntegrationItem(InfrahubPythonTransformItem):
    def runtest(self) -> None:
        input_data = self.session.infrahub_client.query_gql_query(  # type: ignore[attr-defined]
            self.transform_instance.query,
            variables=self.test.spec.get_variables_data(),  # type: ignore[union-attr]
            rebase=self.test.spec.rebase,  # type: ignore[union-attr]
        )
        computed = self.run_transform(input_data)
        differences = self.get_result_differences(computed)

        if computed is not None and differences and self.test.expect == InfrahubTestExpectedResult.PASS:
            raise OutputMatchError(name=self.name, message=differences)
