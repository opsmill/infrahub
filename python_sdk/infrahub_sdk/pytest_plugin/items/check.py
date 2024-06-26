from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Optional

import ujson
from httpx import HTTPStatusError

from infrahub_sdk.checks import get_check_class_instance

from ..exceptions import CheckDefinitionError, CheckResultError
from ..models import InfrahubTestExpectedResult
from .base import InfrahubItem

if TYPE_CHECKING:
    from pytest import ExceptionInfo

    from infrahub_sdk.checks import InfrahubCheck
    from infrahub_sdk.pytest_plugin.models import InfrahubTest
    from infrahub_sdk.schema import InfrahubRepositoryConfigElement


class InfrahubCheckItem(InfrahubItem):
    def __init__(
        self,
        *args: Any,
        resource_name: str,
        resource_config: InfrahubRepositoryConfigElement,
        test: InfrahubTest,
        **kwargs: dict[str, Any],
    ):
        super().__init__(*args, resource_name=resource_name, resource_config=resource_config, test=test, **kwargs)

        self.check_instance: InfrahubCheck

    def instantiate_check(self) -> None:
        self.check_instance = get_check_class_instance(
            check_config=self.resource_config,  # type: ignore[arg-type]
            search_path=self.session.infrahub_config_path.parent,  # type: ignore[attr-defined]
        )

    def run_check(self, variables: dict[str, Any]) -> Any:
        self.instantiate_check()
        return asyncio.run(self.check_instance.run(data=variables))

    def repr_failure(self, excinfo: ExceptionInfo, style: Optional[str] = None) -> str:
        if isinstance(excinfo.value, HTTPStatusError):
            try:
                response_content = ujson.dumps(excinfo.value.response.json(), indent=4)
            except ujson.JSONDecodeError:
                response_content = excinfo.value.response.text
            return "\n".join(
                [
                    f"Failed {excinfo.value.request.method} on {excinfo.value.request.url}",
                    f"Status code: {excinfo.value.response.status_code}",
                    f"Response: {response_content}",
                ]
            )

        return super().repr_failure(excinfo, style=style)


class InfrahubCheckSmokeItem(InfrahubCheckItem):
    def runtest(self) -> None:
        self.instantiate_check()

        for attr in ("query", "validate"):
            if not hasattr(self.check_instance, attr):
                raise CheckDefinitionError(f"Missing attribute or function {attr}")


class InfrahubCheckUnitProcessItem(InfrahubCheckItem):
    def runtest(self) -> None:
        input_data = self.test.spec.get_input_data()  # type: ignore[union-attr]
        passed = self.run_check(input_data)

        if not passed and self.test.expect == InfrahubTestExpectedResult.PASS:
            raise CheckResultError(name=self.name)


class InfrahubCheckIntegrationItem(InfrahubCheckItem):
    def runtest(self) -> None:
        input_data = self.session.infrahub_client.query_gql_query(  # type: ignore[attr-defined]
            self.check_instance.query,
            variables=self.test.spec.get_variables_data(),  # type: ignore[union-attr]
        )
        passed = self.run_check(input_data)

        if not passed and self.test.expect == InfrahubTestExpectedResult.PASS:
            raise CheckResultError(name=self.name)
