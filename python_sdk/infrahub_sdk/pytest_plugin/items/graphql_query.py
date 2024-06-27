from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

import ujson
from httpx import HTTPStatusError

from infrahub_sdk.analyzer import GraphQLQueryAnalyzer

from ..exceptions import OutputMatchError
from ..models import InfrahubTestExpectedResult
from .base import InfrahubItem

if TYPE_CHECKING:
    from pytest import ExceptionInfo


class InfrahubGraphQLQueryItem(InfrahubItem):
    def validate_resource_config(self) -> None:
        # Resource name does not need to match against infrahub repo config
        return

    def execute_query(self) -> Any:
        return self.session.infrahub_client.query_gql_query(  # type: ignore[attr-defined]
            self.test.spec.query,  # type: ignore[union-attr]
            variables=self.test.spec.get_variables_data(),  # type: ignore[union-attr]
        )

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

        if isinstance(excinfo.value, OutputMatchError):
            return "\n".join([excinfo.value.message, excinfo.value.differences])

        return super().repr_failure(excinfo, style=style)


class InfrahubGraphQLQuerySmokeItem(InfrahubGraphQLQueryItem):
    def runtest(self) -> None:
        query = (self.session.infrahub_config_path.parent / self.test.spec.path).read_text()  # type: ignore[attr-defined,union-attr]
        GraphQLQueryAnalyzer(query)


class InfrahubGraphQLQueryIntegrationItem(InfrahubGraphQLQueryItem):
    def runtest(self) -> None:
        computed = self.execute_query()
        differences = self.get_result_differences(computed)

        if self.test.spec.output and differences and self.test.expect == InfrahubTestExpectedResult.PASS:  # type: ignore[union-attr]
            raise OutputMatchError(name=self.name, differences=differences)
